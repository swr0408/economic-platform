# -*- coding: utf-8 -*-
"""
相関・先行性分析モジュール (master 限定レポート用)

オフライン・バッチで全経済指標×全銘柄の相関/先行性を計算し、
manifest.json / sections/*.md / matrices/*.csv を生成する。

- loader        : 全キャッシュ/シーズナリティCSVを long-format に正規化 (Phase1)
- engine        : 月次/四半期パネル化・定常化・ラグ相関・Granger・FDR (Phase2)
- registry      : 各国主要指標と主要銘柄の解決 (concept→series_id)
- report_builder: 上記を束ねて成果物を出力 (Phase3)

重要: このモジュールは pandas/scipy/statsmodels に依存する「バッチ専用」。
配信 API (routers/correlation_report.py) は生成済みファイルを読むだけで、
本モジュールを import しない (本番配信を軽量に保つ)。
"""
