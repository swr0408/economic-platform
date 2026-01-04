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

開発コマンド

# サービス再起動
docker-compose restart backend

# 全サービス停止
docker-compose down

# ボリューム含めて削除（データも削除）
docker-compose down -v

# 起動（本番環境）
docker-compose -f docker-compose.simple.yml up -d

# 停止（本番環境）
docker-compose -f docker-compose.simple.yml down

# 再ビルドして起動（本番環境）
docker-compose -f docker-compose.simple.yml up --build -d

# 強制再ビルドして起動（本番環境）
docker-compose -f docker-compose.simple.yml up -d --build --force-recreate

# 起動（開発環境）
docker-compose up -d

# 停止（開発環境）
docker-compose down

# 再ビルドして起動（開発環境）
docker-compose up --build -d

# 強制再ビルドして起動（開発環境）
docker-compose up -d --build --force-recreate

# ログ確認
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f backend
docker-compose logs -f frontend

本番→開発への切り替え手順
# 1. 本番環境を停止
docker-compose -f docker-compose.simple.yml down

# 2. 開発環境を起動（初回はビルドが必要）
docker-compose up -d --build

# または強制再ビルド
docker-compose up -d --build --force-recreate


実際の開発環境
# 開発環境でbackend + キャッシュを起動
docker-compose up -d postgres redis backend

# frontendはホストで実行
cd frontend
npm run dev

# キャッシュ削除
curl -X DELETE http://localhost:8000/api/usa/policy/dashboard/cache

# ログ確認
docker logs economic-frontend
docker logs economic-backend

#root@DESKTOP-HCCRK6V:/mnt/c/Users/owner/Desktop/economic-platform/backendで全ての依存関係を再インストール
pip install -r requirements.txt
#確認
python -c "import fitz; print(f'PyMuPDF: {fitz.version}')"
python -c "from PIL import Image; print('Pillow: OK')"
python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; print('APScheduler: OK')"

# すべてのダッシュボードキャッシュをクリア
docker exec economic-platform-redis redis-cli KEYS "usa:*:dashboard:*" | xargs -I {} docker exec economic-platform-redis redis-cli DEL {}

# すべてのinvestingキャッシュをクリア
docker exec economic-platform-redis redis-cli KEYS "investing:*" | xargs -I {} docker exec economic-platform-redis redis-cli DEL {}