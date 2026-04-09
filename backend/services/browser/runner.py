"""BrowserRunner 抽象基底クラスと関連 dataclass。

このモジュールは「ブラウザを 1 つ起動して、URL を開いて、スクショを撮って、
閉じる」という最小ユースケースを表現する。Playwright / Selenium はこの
インターフェースの実装として隠蔽される。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class BrowserConfig:
    """ブラウザ起動時のグローバル設定。

    既存サービスの利用パターンを踏まえた最小セット:
        - viewport: 既存は (1920,1080) / (1366,768) / (1280,1024) などが混在
        - user_agent: Bot 検出回避用に固定 UA を渡したいケース
        - locale: zh-CN / ja-JP など、地域依存ページで重要
        - timezone_id: BoJ など JST 固定で取りたいページ
        - default_navigation_timeout_ms: page.goto() のデフォルト
        - default_action_timeout_ms: クリック / 待機のデフォルト
        - headless: 開発時に False にしてデバッグできる余地を残す
        - extra_browser_args: --no-sandbox 等を渡せる脱出口
    """

    viewport: tuple[int, int] = (1920, 1080)
    user_agent: Optional[str] = None
    locale: Optional[str] = None
    timezone_id: Optional[str] = None
    default_navigation_timeout_ms: int = 60_000
    default_action_timeout_ms: int = 30_000
    headless: bool = True
    extra_browser_args: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ScreenshotRequest:
    """1 枚のスクショ取得リクエスト。

    Attributes:
        url: 開くページの URL
        output_path: 保存先の絶対パス (.png 推奨)。
                     None の場合は bytes 返却モード。
        wait_selector: ページ準備完了とみなす CSS セレクタ (任意)
        wait_for_load_state: "load" | "domcontentloaded" | "networkidle"
        wait_after_load_ms: ロード完了後の追加待機 (アニメーション/レンダ完了用)
        clip_selector: スクショ対象を絞る CSS セレクタ (任意, 指定時は要素のみ)
        full_page: 全ページスクショ取得 (clip_selector と排他)
        pre_click_selectors: スクショ前にクリックするセレクタ列
                             (Cookie バナー閉じる等)
        viewport_override: このリクエストだけビューポートを変えたい場合
        scroll_into_view: clip_selector に対して scrollIntoView を行うか
        pre_screenshot_js: スクショ直前にページ上で実行する JS 式 (任意)
                           例: 凡例位置やレイアウト調整など。失敗は無視される
                           (デバッグログのみ)。
        wait_after_pre_js_ms: pre_screenshot_js 実行後の追加待機 (描画完了用)
    """

    url: str
    output_path: Optional[str] = None
    wait_selector: Optional[str] = None
    wait_for_load_state: str = "networkidle"
    wait_after_load_ms: int = 0
    clip_selector: Optional[str] = None
    full_page: bool = False
    pre_click_selectors: tuple[str, ...] = field(default_factory=tuple)
    viewport_override: Optional[tuple[int, int]] = None
    scroll_into_view: bool = False
    pre_screenshot_js: Optional[str] = None
    wait_after_pre_js_ms: int = 0


@dataclass(frozen=True)
class ScreenshotResult:
    """スクショ取得の結果。

    Attributes:
        path: 保存先パス (output_path 指定時のみ)
        data: PNG バイト列 (output_path 未指定時のみ)
        size_bytes: ファイルサイズ
        url: 実際にスクショを撮った URL (リダイレクト後)
    """

    path: Optional[str]
    data: Optional[bytes]
    size_bytes: int
    url: str


@dataclass
class ExtractRequest:
    """ページから DOM テキスト / HTML / JS 評価結果を取得するリクエスト。

    既存の「データスクレイピング」型サービス (eurex_ois / boj_lending /
    inflation_nowcasting / ny_option_cut) を BrowserRunner 経由に統一する
    ために、ScreenshotRequest と並列で用意する。

    Attributes:
        url: 開くページの URL
        wait_selector: ページ準備完了とみなす CSS セレクタ
        wait_for_load_state: "load" | "domcontentloaded" | "networkidle"
        wait_after_load_ms: ロード完了後の追加待機
        pre_click_selectors: 事前クリック (Cookie バナー閉じる等)
        text_selectors: 取得したい要素の CSS セレクタ列
                        → ExtractResult.texts に dict[selector, list[str]] で返す
        html_selectors: 要素の outer HTML を取得したい CSS セレクタ列
                        → ExtractResult.html に dict[selector, list[str]] で返す
        evaluate_js: ページ上で実行する JS 式 (任意)
                     → ExtractResult.evaluated に JSON-serializable で返す
        viewport_override: ビューポート上書き
    """

    url: str
    wait_selector: Optional[str] = None
    wait_for_load_state: str = "networkidle"
    wait_after_load_ms: int = 0
    pre_click_selectors: tuple[str, ...] = field(default_factory=tuple)
    text_selectors: tuple[str, ...] = field(default_factory=tuple)
    html_selectors: tuple[str, ...] = field(default_factory=tuple)
    evaluate_js: Optional[str] = None
    viewport_override: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class ExtractResult:
    """ExtractRequest の結果。

    Attributes:
        url: 実際にアクセスした URL (リダイレクト後)
        texts: text_selectors → 取得テキスト列の dict[selector, list[str]]
        html: html_selectors → outerHTML 列の dict[selector, list[str]]
        evaluated: evaluate_js の戻り値 (JSON-serializable, 未指定時は None)
    """

    url: str
    texts: dict
    html: dict
    evaluated: object


class BrowserRunner(ABC):
    """ブラウザ実行の抽象インターフェース。

    `with` 構文で使うことを前提とする (`__enter__` / `__exit__` を実装側に
    要求する)。`contextlib.AbstractContextManager` を継承すると ABC との
    MRO が衝突するため、自前で context manager 風 API を定義している。

    実装は context manager として使うことを前提とする:

        with PlaywrightRunner(BrowserConfig()) as runner:
            result = runner.screenshot(ScreenshotRequest(...))

    実装側の責務:
        - __enter__ でブラウザ/コンテキスト/ページを起動
        - __exit__ で確実に終了 (例外時もリソース解放)
        - screenshot() の中では `concurrency.browser_semaphore` を取得しない。
          セマフォ取得は呼び出し側 (screenshot_helper など) の責務とする。
          (= runner 自体は薄く保ち、単体テストしやすくする)
    """

    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self.config: BrowserConfig = config or BrowserConfig()

    @abstractmethod
    def screenshot(self, request: ScreenshotRequest) -> ScreenshotResult:
        """1 ページのスクショを取得する。

        Raises:
            BrowserNavigationError: URL 取得自体に失敗
            BrowserTimeoutError: セレクタ待機等のタイムアウト
            BrowserRunnerError: その他失敗
        """
        raise NotImplementedError

    def extract(self, request: ExtractRequest) -> ExtractResult:
        """1 ページから DOM テキスト / HTML / JS 評価結果を取得する。

        スクリーンショットを撮らずデータだけ欲しい場合に使う。
        サブクラスでオプショナルに実装する (デフォルトは NotImplementedError)。

        Raises:
            BrowserNavigationError: URL 取得自体に失敗
            BrowserTimeoutError: セレクタ待機等のタイムアウト
            BrowserRunnerError: その他失敗
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement extract()"
        )

    @abstractmethod
    def __enter__(self) -> "BrowserRunner":
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        raise NotImplementedError
