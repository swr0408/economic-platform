#!/usr/bin/env bash
# ============================================================================
# restore_db.sh - PostgreSQL + Redis リストア
# ============================================================================
# 用途:
#   backup_db.sh で作成したバックアップからリストアする。
#
# 使い方:
#   bash scripts/restore_db.sh                          # 最新の PG バックアップをリストア
#   bash scripts/restore_db.sh /backup/econalpha/econalpha_pg_20260410_040000.sql.gz
#   RESTORE_REDIS=1 bash scripts/restore_db.sh          # Redis も最新からリストア
#
# 注意:
#   - リストア前に既存データは DROP → 再作成される
#   - 本番で実行する前に必ず現時点のバックアップを取ること
# ============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backup/econalpha}"
PG_CONTAINER="${PG_CONTAINER:-econalpha-prod-db}"
REDIS_CONTAINER="${REDIS_CONTAINER:-econalpha-prod-redis}"
DB_NAME="${DB_NAME:-economic_platform}"
DB_USER="${DB_USER:-postgres}"
RESTORE_REDIS="${RESTORE_REDIS:-0}"

# ---------- PostgreSQL リストア ----------

PG_FILE="${1:-}"

if [ -z "${PG_FILE}" ]; then
  # 引数なし → 最新のバックアップを自動選択
  PG_FILE=$(ls -t "${BACKUP_DIR}"/econalpha_pg_*.sql.gz 2>/dev/null | head -1)
  if [ -z "${PG_FILE}" ]; then
    echo "ERROR: No PostgreSQL backup found in ${BACKUP_DIR}" >&2
    exit 1
  fi
fi

echo "[$(date)] Restoring PostgreSQL from: ${PG_FILE}"
echo "[$(date)] WARNING: This will drop and recreate the database '${DB_NAME}'"
read -p "Continue? (y/N): " CONFIRM
if [ "${CONFIRM}" != "y" ] && [ "${CONFIRM}" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

# DB を drop → create
docker exec "${PG_CONTAINER}" \
  psql -U "${DB_USER}" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" 2>/dev/null || true

docker exec "${PG_CONTAINER}" \
  psql -U "${DB_USER}" -c "DROP DATABASE IF EXISTS ${DB_NAME};"

docker exec "${PG_CONTAINER}" \
  psql -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};"

# TimescaleDB 拡張を有効化
docker exec "${PG_CONTAINER}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# リストア
gunzip -c "${PG_FILE}" | docker exec -i "${PG_CONTAINER}" \
  psql -U "${DB_USER}" -d "${DB_NAME}" --single-transaction

echo "[$(date)] PostgreSQL restore complete"

# ---------- Redis リストア (オプション) ----------

if [ "${RESTORE_REDIS}" = "1" ]; then
  REDIS_FILE=$(ls -t "${BACKUP_DIR}"/econalpha_redis_*.rdb.gz 2>/dev/null | head -1)
  if [ -z "${REDIS_FILE}" ]; then
    echo "[$(date)] No Redis backup found in ${BACKUP_DIR}, skipping"
  else
    echo "[$(date)] Restoring Redis from: ${REDIS_FILE}"

    # 一時ファイルに解凍
    TMP_RDB="${BACKUP_DIR}/_tmp_restore.rdb"
    gunzip -c "${REDIS_FILE}" > "${TMP_RDB}"

    # Redis を停止 → rdb を差し替え → 再起動
    docker stop "${REDIS_CONTAINER}"
    docker cp "${TMP_RDB}" "${REDIS_CONTAINER}:/data/dump.rdb"
    docker start "${REDIS_CONTAINER}"
    rm -f "${TMP_RDB}"

    echo "[$(date)] Redis restore complete"
  fi
fi

echo "[$(date)] Restore finished"
