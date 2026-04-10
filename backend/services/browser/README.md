# `backend.services.browser`

ブラウザ自動化 (Playwright / Selenium) を 1 つの抽象に統合するパッケージ。

## このパッケージの目的

EconAlpha は現在 18 個の screenshot / scraping サービスを抱えていて、内訳は以下:

- **Selenium 直接利用: 13 ファイル** (chromium + chromium-driver に依存)
- **Playwright 直接利用: 5 ファイル** (chromium + firefox + ブラウザ依存ライブラリ)

これを OCI Always Free (Ampere A1, ARM64) に持っていく際、Selenium chromedriver の
ARM64 公式バイナリが存在しないため詰むのが既知の課題。

このパッケージは:

1. **共通インターフェース** (`BrowserRunner` ABC) を提供して、サービスから直接
   Playwright/Selenium API を呼ばないよう徐々に移行する。
2. **Playwright を「正」**、Selenium を「廃止予定の skeleton」と位置付ける。
3. 並列実行数をプロセス全体で制限する (`concurrency.browser_semaphore`)。
4. 将来 `browser-worker` コンテナへ分離する場合の境界面を、コードに先に書いておく。

**重要**: 既存 18 サービスは現時点で 1 行も変更しない。新規 / 移行は 1 つずつ。

## ファイル構成

```
backend/services/browser/
├── __init__.py              ← 公開 API (BrowserRunner / take_screenshot 等)
├── runner.py                ← BrowserRunner ABC + dataclass (BrowserConfig 等)
├── playwright_runner.py     ← 既定実装 (sync_api ベース)
├── selenium_runner.py       ← 廃止予定のスケルトン (NotImplementedError)
├── screenshot_helper.py     ← 高レベルファサード (take_screenshot)
├── concurrency.py           ← プロセス内セマフォ (default 2 並列)
├── exceptions.py            ← BrowserRunnerError 等の例外
└── README.md                ← (このファイル)
```

関連:
- `backend/Dockerfile.browser-worker` … Playwright 公式 multi-arch イメージベース
- `backend/tests/test_browser_runner.py` … contract test

## 使い方

### 1. 1 ファイル 1 スクショ (推奨パターン)

```python
from backend.services.browser import take_screenshot, ScreenshotRequest

result = take_screenshot(ScreenshotRequest(
    url="https://truflation.com/marketplace/us-inflation-rate",
    output_path="/app/screenshots/truflation_us_cpi_1y.png",
    wait_selector="canvas",            # チャート描画を待つ
    wait_after_load_ms=2_000,          # アニメ完了用に 2 秒追加待機
    viewport_override=(1440, 900),
))
print(result.path, result.size_bytes)
```

`take_screenshot` は内部で:
1. プロセス共有セマフォ (`browser_semaphore`, default 2 並列) を取得
2. 既定 runner (`PlaywrightRunner`, chromium) を起動
3. 1 ページだけ開いてスクショ
4. 確実にブラウザを閉じる

### 2. 複数枚を 1 ブラウザで撮る

```python
from backend.services.browser import (
    BrowserConfig, ScreenshotRequest, get_default_runner,
)
from backend.services.browser.concurrency import browser_semaphore

cfg = BrowserConfig(viewport=(1920, 1080), locale="zh-CN")
with browser_semaphore:
    with get_default_runner(config=cfg) as runner:
        runner.screenshot(ScreenshotRequest(
            url="https://example.com/a",
            output_path="/tmp/a.png",
        ))
        runner.screenshot(ScreenshotRequest(
            url="https://example.com/b",
            output_path="/tmp/b.png",
        ))
```

### 3. 例外ハンドリング

```python
from backend.services.browser import (
    BrowserNavigationError, BrowserTimeoutError, BrowserRunnerError,
)

try:
    take_screenshot(req)
except BrowserTimeoutError:
    # セレクタ待機 / ナビゲーションタイムアウト → リトライ可
    ...
except BrowserNavigationError:
    # DNS / TLS / HTTP エラー → リトライ可
    ...
except BrowserRunnerError:
    # その他 (Playwright 未インストール等) → 設定ミスを疑う
    ...
```

## 設計上の決定

### Playwright を「正」とした理由

| 観点 | Playwright | Selenium |
|------|-----------|----------|
| ARM64 公式バイナリ | ◎ (Chromium / Firefox / Webkit すべて) | △ (chromedriver はディストリ依存) |
| 公式 Docker (multi-arch) | ◎ `mcr.microsoft.com/playwright/python` | × |
| API の整理度 | ◎ `wait_for_selector` 等が一級 | △ explicit wait を毎回書く必要 |
| iframe / shadow DOM | ◎ | △ |
| 既存社内実績 | ◎ `cme_fedwatch_screenshot_service.py` 等 | ◎ 13 ファイル (移行対象) |

### なぜ `runner` 自体ではセマフォを取得しないか

- `runner` は薄く保ち、単体テストでセマフォを意識せず使えるようにしたい
- 「1 ブラウザで複数スクショ」の場合、外側で 1 度だけ取得すれば十分
- セマフォ取得は `screenshot_helper` (= 高レベルファサード) の責務

### 並列上限のデフォルト = 2

OCI Always Free (1 OCPU / 6GB) で Chromium を 3 つ以上同時に起動するとメモリ圧迫の
リスクがあるため。環境変数 `BROWSER_RUNNER_CONCURRENCY` で上書き可能。

### `selenium_runner.py` を残した理由

- `BrowserRunner` ABC が「contract」であることを示す 2 つ目の実装として
- 過渡期に Selenium が必要な場合の取っ掛かり
- OCI 移行後 = Selenium 完全廃止後にこのファイルは削除予定

## 移行ガイド (既存サービスを Playwright runner に置き換える)

例: `cn_baidu_migration_screenshot_service.py` の典型パターン

**Before** (Selenium 直接):
```python
from selenium import webdriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)
try:
    driver.get(url)
    time.sleep(5)
    driver.save_screenshot(output_path)
finally:
    driver.quit()
```

**After** (browser package):
```python
from backend.services.browser import take_screenshot, ScreenshotRequest

take_screenshot(ScreenshotRequest(
    url=url,
    output_path=output_path,
    wait_after_load_ms=5_000,
))
```

セレクタを既知のパターンで使っている場合は `wait_selector` を渡して
`time.sleep` を排除すること。

### スクショ前に JS でレイアウト調整したい場合

`pre_screenshot_js` を使う:

```python
take_screenshot(ScreenshotRequest(
    url="https://qianxi.baidu.com/#/",
    output_path="/app/screenshots/baidu_migration.png",
    wait_selector=".mgs-line",
    wait_after_load_ms=8_000,
    clip_selector=".mgs-line",
    scroll_into_view=True,
    pre_screenshot_js="""
        var root = document.querySelector('.mgs-line');
        if (root) { root.style.height = '500px'; }
    """,
    wait_after_pre_js_ms=2_000,
))
```

実例: [services/china/cn_baidu_migration_screenshot_service.py](../china/cn_baidu_migration_screenshot_service.py)

### データ抽出だけしたい場合 (スクショ不要)

`extract_page` + `ExtractRequest` を使う:

```python
from backend.services.browser import extract_page, ExtractRequest

result = extract_page(ExtractRequest(
    url="https://example.com/data",
    wait_selector="table.results",
    text_selectors=("table.results tr td.value",),
    evaluate_js="document.querySelector('h1').innerText",
))
print(result.texts["table.results tr td.value"])  # list[str]
print(result.evaluated)  # h1 のテキスト
```

### リトライ付き

`take_screenshot_with_retry` は `BrowserTimeoutError` / `BrowserNavigationError`
のみリトライする (設定エラー等はリトライ不要なので即 raise):

```python
from backend.services.browser import take_screenshot_with_retry

result = take_screenshot_with_retry(
    request,
    max_attempts=3,
    initial_backoff_seconds=2.0,
    backoff_multiplier=2.0,  # 2s → 4s → 8s
)
```

## 並列実行とスケジュール上の注意

APScheduler の現状 (browser を使うジョブのみ抜粋):

| JST 時刻 | スケジューラ | ブラウザ使用 |
|---|---|---|
| 15:30 | cn_fixing_repo_rate, cn_shibor | Selenium → 移行候補 |
| 17:00 | cn_central_parity, sge_gold | Selenium → 移行候補 |
| 18:00 | cn_baidu_migration ✅ (移行済), cn_government_bond_issuance | mixed |

`BROWSER_RUNNER_CONCURRENCY=2` (デフォルト) では問題なし。OCI で
`=1` に絞ったときは同時刻ジョブの 2 本目が 1 本目の完了待ちで遅延する
(エラーにはならない)。

**注意**: 上の表のうち `cn_shibor` / `cn_fixing_repo_rate` /
`cn_government_bond_issuance` / `cn_central_parity` / `sge_gold` は
実際には HTTP API / HTML スクレイピングのみで browser を起動しないので
セマフォを消費しない。実際にセマフォを取り合うのは `cn_baidu_migration`
(18:00) と将来移行する `cn_li_keqiang_index` / `cn_credit_impulse`
スケジューラ (現状未投入) のみ。

## 残タスク (cloud 移行に向けて)

| # | 状態 | タスク |
|---|---|---|
| 1 | ✅ DONE | `backend/services/browser/` パッケージ整備 |
| 2 | ✅ DONE | `Dockerfile.browser-worker` (Playwright 公式 multi-arch base) |
| 3 | ✅ DONE | `docker-compose.oci.yml` (ARM64 / mem_limit / shm_size) |
| 4 | ✅ DONE | `extract()` API 追加 (DOM テキスト / HTML / evaluate) |
| 5 | ✅ DONE | `pre_screenshot_js` フィールド追加 (レイアウト調整用) |
| 6 | ✅ DONE | `take_screenshot_with_retry` ヘルパー |
| 7 | ✅ DONE | 既存 18 サービスの段階移行 (16/16 完了 — 全サービスが BrowserRunner 経由に統一) |
| 8 | ⏳ 未着手 | Selenium を `Dockerfile.simple` から削除 (全移行完了 — 削除可能) |
| 9 | ✅ 不要 | APScheduler ジョブの時刻分散 (cn_shibor 系は HTTP のみで browser を使わないと判明) |
| 10 | ⏳ 未着手 | `Dockerfile.simple` を `Dockerfile.browser-worker` に統合 or backend/browser-worker 分離 |
| 11 | ✅ DONE | `BrowserRunner` 拡張 (`run_custom_flow` + `context` プロパティ) — boj_lending / cme_fedwatch で使用 |

### 移行進捗 (services/)

| # | サービス | 種類 | 状態 |
|---|---|---|---|
| 1 | china/cn_baidu_migration_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 2 | china/cn_li_keqiang_index_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 3 | china/cn_credit_impulse_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 4 | australia/rba_expectations_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 5 | australia/rba_ois_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 6 | canada/boc_rate_cuts_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 7 | eurozone/ecb_rate_cuts_screenshot_service.py | Selenium → Playwright | ✅ 完了 |
| 8 | eurozone/eurex_ois_service.py | Selenium (extract 型) | ✅ 完了 (evaluate_js) |
| 9 | japan/boj_lending_service.py | Selenium (multi-window CSV) | ✅ 完了 (run_custom_flow / multi-window) |
| 10 | usa/inflation_nowcasting_service.py | Selenium (extract 型) | ✅ 完了 (evaluate_js) |
| 11 | market/ny_option_cut_service.py | Selenium (要素スクショ) | ✅ 完了 (pre_screenshot_js) |
| 12 | usa/cme_fedwatch_screenshot_service.py | Playwright (iframe + Firefox fallback) | ✅ 完了 (run_custom_flow / iframe + Firefox fallback) |
| 13 | usa/opentable_service.py | Playwright (直接利用) | ✅ 完了 (pre_screenshot_js / pre_click_selectors) |
| 14 | usa/us_flights_service.py | Playwright (直接利用) | ✅ 完了 (pre_screenshot_js / pre_click_selectors) |
| 15 | uk/brc_commentary_service.py | Playwright async (直接利用) | ✅ 完了 (extract_page + html_selectors) |
| 16 | japan/boj_meeting_expectations_service.py | Playwright + OCR | ✅ 完了 (bytes モード screenshot + OCR は据え置き) |

### 移行パターン早見表

複数 URL を撮影するサービスは「`get_default_runner()` + `browser_semaphore` を
直接使う」パターンを採用 (起動コスト削減のため):

```python
from services.browser import (
    BrowserConfig, BrowserRunnerError, ScreenshotRequest, get_default_runner,
)
from services.browser.concurrency import browser_semaphore

with browser_semaphore:
    with get_default_runner(config=BrowserConfig(...)) as runner:
        for url, output_path in items:
            try:
                runner.screenshot(ScreenshotRequest(url=url, output_path=output_path, ...))
            except BrowserRunnerError as e:
                logger.error(f"capture failed: {e}")
```

1 URL 1 撮影で良いサービスは `take_screenshot_with_retry` で十分。

### bytes モード (ファイル保存せず PNG バイト列を取得)

OCR や API 経由で画像を直接渡したいケースは `output_path=None` で実行する:

```python
from services.browser import ScreenshotRequest, take_screenshot

result = take_screenshot(ScreenshotRequest(
    url="https://example.com/table",
    output_path=None,  # ← bytes モード
    clip_selector="[data-table='1']",
    pre_screenshot_js="...",  # 対象要素にマーキング
))
png_bytes = result.data  # bytes (Pillow / Tesseract に渡せる)
```

実例: [services/japan/boj_meeting_expectations_service.py](../japan/boj_meeting_expectations_service.py)
(Tesseract OCR にそのまま渡す)

### カスタムフロー (multi-window / form / iframe)

`screenshot()` / `extract()` では表現できない複雑なフロー用。
`run_custom_flow` でコールバックに Playwright `BrowserContext` を渡す:

```python
from services.browser import BrowserConfig, run_custom_flow

def my_flow(context):
    page = context.new_page()
    page.goto("https://example.com")
    page.fill("#search", "query")
    page.click("button[type=submit]")

    # ポップアップを捕捉
    with context.expect_page() as popup_info:
        page.click("a[target=_blank]")
    popup = popup_info.value
    popup.wait_for_load_state("networkidle")

    result = popup.locator("h1").inner_text()
    popup.close()
    page.close()
    return result

data = run_custom_flow(my_flow, config=BrowserConfig(locale="ja-JP"))
```

セマフォ管理・ブラウザのライフサイクル管理は `run_custom_flow` が担当。

実例:
- [services/japan/boj_lending_service.py](../japan/boj_lending_service.py) (multi-window CSV 取得)
- [services/usa/cme_fedwatch_screenshot_service.py](../usa/cme_fedwatch_screenshot_service.py) (iframe 内要素スクショ)

### 解決済み: run_custom_flow による複雑フロー対応

以下 2 サービスは `run_custom_flow()` API の追加により移行完了:

**`japan/boj_lending_service.py`** (Selenium → Playwright 移行完了):
- `run_custom_flow` で `BrowserContext` を直接操作し、複数 window フロー
  (`context.expect_page()` でポップアップを捕捉) を実現
- CSV URL 取得後は従来通り `requests.get()` でダウンロード

**`usa/cme_fedwatch_screenshot_service.py`** (Playwright 直接 → run_custom_flow 移行完了):
- `run_custom_flow` で `page.frames` を使い iframe 内の操作を実現
- Chromium → Firefox フォールバックは `browser_type` パラメータで切替
- iframe 内の Aggregated タブクリック + 要素スクショのロジックはそのまま維持
