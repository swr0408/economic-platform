## ローカル開発環境セットアップ

### 前提条件
- Docker Desktop インストール済み
- Git インストール済み
- Node.js 20+ (フロントエンド開発用)
- Python 3.12.7+ (バックエンド開発用)

### 手順

1. **リポジトリクローン**
```bash
git clone https://github.com/your-org/economic-platform.git
cd economic-platform

環境変数設定
cp .env.example .env
# .envファイルを編集してAPIキーを設定

Docker Composeで全サービス起動
docker-compose up -d

データベース初期化
# マイグレーション実行
docker-compose exec backend alembic upgrade head

# TimescaleDB拡張を有効化
docker-compose exec postgres psql -U postgres -d economic_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

アクセス確認
Frontend: http://localhost:3000
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs
Celery Flower: http://localhost:5555

開発コマンド
# ログ確認
docker-compose logs -f backend
docker-compose logs -f celery-worker

# サービス再起動
docker-compose restart backend

# 全サービス停止
docker-compose down

# ボリューム含めて削除（データも削除）
docker-compose down -v