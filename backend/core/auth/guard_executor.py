"""認証ガードミドルウェア専用スレッドプール

read/write ガードの `_extract_role` は JWT デコードに加えて同期 Redis 呼び出し
(is_jti_revoked / get_force_logout_after) を行う。これをイベントループ上で直接
実行すると、Redis 応答が遅延した瞬間に全リクエスト処理が停止する
(2026-06-13 障害: ループが sock.recv で 10 秒超ブロック → リロードの graceful
shutdown が永久に完了せず /api/auth/login 含む全エンドポイントがタイムアウト)。

デフォルトの executor はダッシュボードの重い load_all (run_in_executor) と共有
されており、そちらの混雑時に認証チェックまで待たされる。認証専用の小さな
プールに隔離することで、両者が互いに飢餓しないようにする。
"""
from concurrent.futures import ThreadPoolExecutor

AUTH_GUARD_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="auth-guard")
