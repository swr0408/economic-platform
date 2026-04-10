#!/usr/bin/env bash
# ============================================================================
# backup_db.sh - PostgreSQL + Redis 日次バックアップ
# ============================================================================
# 用途:
#   docker-compose 環境の PostgreSQL と Redis をバックアップする。
#   PostgreSQL: pg_dump → gzip
#   Redis: BGSAVE → appendonly.aof + dump.rdb をコピー
#   7 世代まで保持し、古いものは自動削除する。
#
# 前提:
#   - docker compose が使える環境で実行する
#   - postgres / redis コンテナが起動している
#
# cron 設定例 (毎日 AM 4:00 JST):
#   0 4 * * * cd /home/ubuntu/economic-platform && bash scripts/backup_db.sh >> /var/log/econalpha-backup.log 2>&1
# ============================================================================
set -euo pipefail

# 設定
BACKUP_DIR="${BACKUP_DIR:-/backup/econalpha}"
KEEP_DAYS="${KEEP_DAYS:-7}"
PG_CONTAINER="${PG_CONTAINER:-econalpha-prod-db}"
REDIS_CONTAINER="${REDIS_CONTAINER:-econalpha-prod-redis}"
DB_NAME="${DB_NAME:-economic_platform}"
DB_USER="${DB_USER:-postgres}"

# バックアップディレクトリ作成
mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# ---- PostgreSQL ----
PG_FILE="${BACKUP_DIR}/econalpha_pg_${TIMESTAMP}.sql.gz"
echo "[$(date)] Starting PostgreSQL backup: ${PG_FILE}"

docker exec "${PG_CONTAINER}" \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" --no-owner --no-privileges \
  | gzip > "${PG_FILE}"

PG_SIZE=$(du -sh "${PG_FILE}" | cut -f1)
echo "[$(date)] PostgreSQL backup complete: ${PG_FILE} (${PG_SIZE})"

# ---- Redis ----
REDIS_FILE="${BACKUP_DIR}/econalpha_redis_${TIMESTAMP}.rdb.gz"
echo "[$(date)] Starting Redis backup: ${REDIS_FILE}"

# BGSAVE をトリガーして完了を待つ
docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE > /dev/null 2>&1 || true
sleep 2

# dump.rdb をコンテナからコピー
docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${BACKUP_DIR}/_tmp_dump.rdb" 2>/dev/null \
  && gzip -c "${BACKUP_DIR}/_tmp_dump.rdb" > "${REDIS_FILE}" \
  && rm -f "${BACKUP_DIR}/_tmp_dump.rdb" \
  && REDIS_SIZE=$(du -sh "${REDIS_FILE}" | cut -f1) \
  && echo "[$(date)] Redis backup complete: ${REDIS_FILE} (${REDIS_SIZE})" \
  || echo "[$(date)] Redis backup skipped (dump.rdb not found or copy failed)"

# ---- 古いバックアップを削除 ----
DELETED=$(find "${BACKUP_DIR}" -name "econalpha_*" -mtime +${KEEP_DAYS} -delete -print | wc -l)
if [ "${DELETED}" -gt 0 ]; then
  echo "[$(date)] Deleted ${DELETED} old backup(s) (older than ${KEEP_DAYS} days)"
fi

echo "[$(date)] Backup finished successfully"
