# OpenTable ローカル自動キャプチャ（半自動）

米国レストラン予約件数（OpenTable Seated Diners, `country/usa/economy#opentable`）を
**実物の Google Chrome で自動キャプチャし、バックエンドへ自動投稿**するローカルツール。

## なぜローカル？

OpenTable の [State of the Industry](https://www.opentable.com/state-of-industry) は
**Akamai Bot Manager** 配下で、bundled Chromium / データセンターIP / OCI ARM64
(=Google Chrome非搭載) からは遮断される。**実 Chrome + 住宅IP** でのみ突破できるため、
サーバ常駐の完全自動化はできない。そこで「実 Chrome が動くローカルPC」で撮影し、
既存の `POST /api/usa/opentable/upload`（master限定）へ投稿する半自動運用にする。

- 撮影対象: 週次ラインチャート `.r9-soti-graph-section` / 月次テーブル `.r9-soti-table-section`
- 週次は地域を `United States`、月次は粒度を `Monthly` に自動切替してから撮影

## 前提

- Python + Playwright（`pip install playwright`。ブラウザ同梱は不要、実 Chrome を使う）
- **Google Chrome 本体**がインストール済み（`channel='chrome'` で使用）
- バックエンドが稼働（既定 `http://localhost:8000`）

## セットアップ

```powershell
cd backend\scripts\opentable_capture

# 1) 起動バッチを用意して master 認証情報を設定
copy run_opentable_capture.example.bat run_opentable_capture.bat
notepad run_opentable_capture.bat        # ECONALPHA_PASSWORD を設定

# 2) まず撮影だけ試す（アップロードしない。png がこのフォルダに保存される）
python opentable_local_capture.py --dry-run

# 3) 本番実行を手動で確認（撮影→ログイン→アップロード）
.\run_opentable_capture.bat

# 4) 日次タスクに登録（既定 毎日 09:00）
powershell -ExecutionPolicy Bypass -File .\register_opentable_task.ps1
#   時刻変更例: -File .\register_opentable_task.ps1 -At 12:30
```

登録後すぐ試す:
```powershell
Start-ScheduledTask -TaskName "EconAlpha OpenTable Capture"
```

解除:
```powershell
Unregister-ScheduledTask -TaskName "EconAlpha OpenTable Capture" -Confirm:$false
```

## 設定（環境変数 / run_opentable_capture.bat）

| 変数 | 既定 | 説明 |
|---|---|---|
| `ECONALPHA_API_BASE` | `http://localhost:8000` | バックエンドURL |
| `ECONALPHA_USERNAME` | — | master ユーザー名 |
| `ECONALPHA_PASSWORD` | — | master パスワード |
| `OPENTABLE_WEEKLY_GEOGRAPHY` | `United States` | 週次チャートの地域（`Global` 等に変更可） |
| `OPENTABLE_CHROME_CHANNEL` | `chrome` | Playwright チャンネル |
| `OPENTABLE_HEADLESS` | `1` | `0` でブラウザ表示（デバッグ） |

## トラブルシューティング

- **`Google Chrome の起動に失敗`**: 実 Chrome 未インストール。Chrome を入れる、
  または `OPENTABLE_CHROME_CHANNEL=chrome-beta` 等に変更。
- **`login failed: HTTP 401`**: master 認証情報が誤り。`run_opentable_capture.bat` を確認。
- **`upload failed: HTTP 401`**: そのユーザーに master 権限が無い。
- **セクションが撮れない / 空画像**: OpenTable のDOM改定でセレクタが変わった可能性。
  `--headful` で表示して確認し、`opentable_local_capture.py` の
  `WEEKLY_SECTION` / `MONTHLY_SECTION` を更新する。
- ログ: `opentable_capture.log`（このフォルダ）。

## 注意

- `run_opentable_capture.bat`（パスワード含む）と `opentable_capture.log`、
  撮影 png は **.gitignore 済み**でコミットされない。
- タスクは既定で「ユーザーがログオン中のみ実行」。PC が起動していれば
  `StartWhenAvailable` により、指定時刻に起動していなくても次回起動時に補完実行する。
