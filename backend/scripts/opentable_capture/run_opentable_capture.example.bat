@echo off
REM ============================================================================
REM OpenTable ローカル自動キャプチャ 起動バッチ（タスクスケジューラから実行）
REM
REM 使い方:
REM   1) このファイルを run_opentable_capture.bat にコピー
REM   2) 下の ECONALPHA_PASSWORD に master のパスワードを設定
REM   3) register_opentable_task.ps1 で日次タスクに登録
REM
REM ※ run_opentable_capture.bat は認証情報を含むため .gitignore 済み（コミットしない）
REM ============================================================================

REM --- バックエンドURL（ローカル稼働なら既定のままでOK） ---
set ECONALPHA_API_BASE=http://localhost:8000

REM --- master 認証情報（アップロードに master 権限が必要） ---
set ECONALPHA_USERNAME=econalpha_master
set ECONALPHA_PASSWORD=ここにmasterのパスワードを入れる

REM --- 週次チャートの地域（"United States" 推奨 / "Global" 等に変更可） ---
set OPENTABLE_WEEKLY_GEOGRAPHY=United States

REM --- Playwright チャンネル（実物 Google Chrome を使う） ---
set OPENTABLE_CHROME_CHANNEL=chrome

REM このバッチのあるフォルダへ移動して実行
cd /d "%~dp0"
python opentable_local_capture.py

REM 終了コードをそのまま返す（タスクスケジューラの成否判定用）
exit /b %ERRORLEVEL%
