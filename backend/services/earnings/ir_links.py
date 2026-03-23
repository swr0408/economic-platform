"""IR page links for target companies.

Each entry: ticker_upper -> {"home": str, "results": str, "notes": str (optional)}
"""

IR_LINKS: dict[str, dict[str, str]] = {
    # -----------------------------------------------------------------------
    # USA
    # -----------------------------------------------------------------------
    "NVDA": {
        "home":    "https://investor.nvidia.com/home/default.aspx",
        "results": "https://investor.nvidia.com/financial-info/financial-reports/",
    },
    "MSFT": {
        "home":    "https://www.microsoft.com/en-us/Investor",
        "results": "https://www.microsoft.com/en-us/Investor/default",
    },
    "AMZN": {
        "home":    "https://ir.aboutamazon.com/",
        "results": "https://ir.aboutamazon.com/quarterly-results/default.aspx",
    },
    "GOOGL": {
        "home":    "https://abc.xyz/investor/",
        "results": "https://abc.xyz/investor/",
        "notes":   "Earnings & Events セクション",
    },
    "META": {
        "home":    "https://investor.fb.com/home/default.aspx",
        "results": "https://investor.fb.com/investor-news/default.aspx",
    },
    "AAPL": {
        "home":    "https://investor.apple.com/",
        "results": "https://investor.apple.com/investor-relations/default.aspx",
        "notes":   "Results release / SEC filings",
    },
    "AVGO": {
        "home":    "https://investors.broadcom.com/",
        "results": "https://investors.broadcom.com/financial-information/quarterly-results",
    },
    "TSLA": {
        "home":    "https://www.tesla.com/",
        "results": "https://investor.apple.com/investor-relations/default.aspx",
        "notes":   "Press releases / Shareholder update PDF",
    },
    "BRK-B": {
        "home":    "https://www.berkshirehathaway.com/",
        "results": "https://www.berkshirehathaway.com/reports.html",
        "notes":   "Annual & Interim Reports / News releases",
    },
    "JPM": {
        "home":    "https://www.jpmorganchase.com/ir",
        "results": "https://www.jpmorganchase.com/ir/quarterly-earnings",
    },
    "V": {
        "home":    "https://investor.visa.com/",
        "results": "https://investor.visa.com/financial-information/quarterly-earnings/default.aspx",
    },
    "MA": {
        "home":    "https://investor.mastercard.com/",
        "results": "https://investor.mastercard.com/financial-information/quarterly-results/default.aspx",
    },
    "LLY": {
        "home":    "https://investor.lilly.com/",
        "results": "https://investor.lilly.com/financial-information/quarterly-results",
    },
    "XOM": {
        "home":    "https://ir.exxonmobil.com/",
        "results": "https://corporate.exxonmobil.com/news/news-releases",
        "notes":   "News releases (results) / corporate news hub",
    },
    "CVX": {
        "home":    "https://www.chevron.com/investors",
        "results": "https://www.chevron.com/investors/press-releases",
    },
    "BAC": {
        "home":    "https://investor.bankofamerica.com/",
        "results": "https://investor.bankofamerica.com/press-releases",
    },
    "GS": {
        "home":    "https://www.goldmansachs.com/investor-relations/",
        "results": "https://www.goldmansachs.com/investor-relations/financials/",
    },
    "WFC": {
        "home":    "https://www.wellsfargo.com/about/investor-relations/",
        "results": "https://www.wellsfargo.com/about/investor-relations/quarterly-earnings/",
    },
    "MS": {
        "home":    "https://www.morganstanley.com/",
        "results": "https://www.morganstanley.com/about-us-ir",
    },
    "NFLX": {
        "home":    "https://ir.netflix.net/ir-overview/profile/default.aspx",
        "results": "https://ir.netflix.net/financials/quarterly-earnings/default.aspx",
    },
    "UNH": {
        "home":    "https://www.uhc.com/",
        "results": "https://www.unitedhealthgroup.com/investors.html",
    },
    "JNJ": {
        "home":    "https://www.investor.jnj.com/overview/default.aspx",
        "results": "https://www.investor.jnj.com/overview/default.aspx",
    },
    "ABBV": {
        "home":    "https://investors.abbvie.com/",
        "results": "https://investors.abbvie.com/",
    },
    "MRK": {
        "home":    "https://www.merck.com/investor-relations/",
        "results": "https://www.merck.com/investor-relations/",
    },
    "CAT": {
        "home":    "https://investors.caterpillar.com/",
        "results": "https://investors.caterpillar.com/overview/default.aspx",
    },
    "GE": {
        "home":    "https://www.ge.com/investor-relations",
        "results": "https://www.ge.com/investor-relations/events-reports",
    },
    "RTX": {
        "home":    "https://www.rtx.com/investors",
        "results": "https://investors.rtx.com/",
    },
    # -----------------------------------------------------------------------
    # Japan (TDnet parallel recommended)
    # -----------------------------------------------------------------------
    "7203.T": {
        "home":    "https://global.toyota/jp/?padid=ag478_from_header",
        "results": "https://global.toyota/jp/ir/?padid=ag478_from_header",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Financial Results / Presentations & transcripts",
    },
    "8306.T": {
        "home":    "https://www.mufg.jp/index.html",
        "results": "https://www.mufg.jp/index.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Financial Information / Presentations",
    },
    "9983.T": {
        "home":    "https://www.fastretailing.com/jp/about/",
        "results": "https://www.fastretailing.com/jp/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Earnings Announcements / Results Summary",
    },
    "9984.T": {
        "home":    "https://group.softbank/ir",
        "results": "https://group.softbank/ir/financials",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Financials and Filings / Presentations",
    },
    "6857.T": {
        "home":    "https://www.advantest.com/ja/investors/",
        "results": "https://www.advantest.com/ja/investors/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Quarterly Financial Results / Earnings Forecast",
    },
    "8035.T": {
        "home":    "https://www.tel.co.jp/",
        "results": "https://www.tel.co.jp/ir/index.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Earnings Release / IR Calendar / library",
    },
    "6501.T": {
        "home":    "https://www.hitachi.com/ja-jp/",
        "results": "https://www.hitachi.com/ja-jp/ir/financial/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Financial Results / Financial Information",
    },
    "6758.T": {
        "home":    "https://www.sony.com/ja/SonyInfo/IR/",
        "results": "https://www.sony.com/ja/SonyInfo/IR/news/archive.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "8316.T": {
        "home":    "https://www.smfg.co.jp/",
        "results": "https://www.smfg.co.jp/investor/highlight/index.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "8411.T": {
        "home":    "https://www.mizuhobank.co.jp/index.html?rt_bn=bk_header",
        "results": "https://www.mizuho-fg.co.jp/investors/financial/tanshin/index.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "8058.T": {
        "home":    "https://www.mitsubishicorp.com/jp/ja/ir/",
        "results": "https://www.mitsubishicorp.com/jp/ja/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "7011.T": {
        "home":    "https://www.mhi.com/jp",
        "results": "https://www.mhi.com/jp/finance",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "4063.T": {
        "home":    "https://www.shinetsu.co.jp/jp/ir/",
        "results": "https://www.shinetsu.co.jp/jp/ir/ir-data/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "9433.T": {
        "home":    "https://www.kddi.com/corporate/ir/",
        "results": "https://www.kddi.com/corporate/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
        "notes":   "Financial Statements / Presentations",
    },
    "6762.T": {
        "home":    "https://www.tdk.com/ja/index.html",
        "results": "https://www.tdk.com/ja/ir/index.html",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "6954.T": {
        "home":    "https://www.fanuc.co.jp/",
        "results": "https://www.fanuc.co.jp/ja/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "4519.T": {
        "home":    "https://www.chugai-pharm.co.jp/",
        "results": "https://www.chugai-pharm.co.jp/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    "5803.T": {
        "home":    "https://www.fujikura.co.jp/ir/",
        "results": "https://www.fujikura.co.jp/ir/",
        "tdnet":   "https://www.release.tdnet.info/inbs/I_main_00.html",
    },
    # -----------------------------------------------------------------------
    # Netherlands
    # -----------------------------------------------------------------------
    "ASML": {
        "home":    "https://www.asml.com/en/investors",
        "results": "https://www.asml.com/en/investors/financial-calendar",
        "notes":   "Financial Calendar / Financial Results",
    },
    "ING": {
        "home":    "https://www.ing.com/Investor-relations.htm",
        "results": "https://ing.com/investors/investor-overview",
    },
    "PRX": {
        "home":    "https://www.prosus.com/investors/",
        "results": "https://www.prosus.com/investors",
    },
    "ASM": {
        "home":    "https://www.asm.com/investors",
        "results": "https://www.asm.com/investors",
    },
    "ADYEN": {
        "home":    "https://investors.adyen.com/",
        "results": "https://investors.adyen.com/",
    },
    "AD": {
        "home":    "https://www.aholddelhaize.com/investors/",
        "results": "https://www.aholddelhaize.com/investors/",
    },
    # -----------------------------------------------------------------------
    # UK
    # -----------------------------------------------------------------------
    "AZN": {
        "home":    "https://www.astrazeneca.com/investor-relations.html",
        "results": "https://www.astrazeneca.com/investor-relations/results-and-presentations.html",
    },
    "HSBA": {
        "home":    "https://www.hsbc.com/investors",
        "results": "https://www.hsbc.com/investors/results-and-announcements",
        "notes":   "Results and announcements / Financial calendar",
    },
    "SHEL": {
        "home":    "https://www.shell.com/investors.html",
        "results": "https://www.shell.com/investors/results-and-reporting.html",
        "notes":   "Results and reporting / Investor presentations",
    },
    "ULVR": {
        "home":    "https://www.unilever.com/",
        "results": "https://www.unilever.com/investors/results-events/",
    },
    "RR": {
        "home":    "https://www.rolls-royce.com/investors.aspx",
        "results": "https://www.rolls-royce.com/investors/results-reports-and-presentations.aspx",
    },
    "GSK": {
        "home":    "https://www.gsk.com/en-gb/investors/",
        "results": "https://www.gsk.com/en-gb/investors/",
    },
    "RIO": {
        "home":    "https://www.riotinto.com/en/invest",
        "results": "https://www.riotinto.com/en/invest/reports",
    },
    "BP": {
        "home":    "https://www.bp.com/en/global/corporate/investors.html",
        "results": "https://www.bp.com/en/global/corporate/investors.html",
    },
    "NG": {
        "home":    "https://www.nationalgrid.com/investors",
        "results": "https://www.nationalgrid.com/investors/events/results-centre",
    },
    # -----------------------------------------------------------------------
    # Switzerland
    # -----------------------------------------------------------------------
    "ROG": {
        "home":    "https://www.roche.com/investors",
        "results": "https://www.roche.com/investors/updates.htm",
        "notes":   "Investor updates / Results event pages",
    },
    "NOVN": {
        "home":    "https://www.novartis.com/investors",
        "results": "https://www.novartis.com/investors/financial-data/quarterly-results",
    },
    "NESN": {
        "home":    "https://www.nestle.com/investors",
        "results": "https://www.nestle.com/investors",
    },
    "UBSG": {
        "home":    "https://www.ubs.com/global/en/investor-relations.html",
        "results": "https://www.ubs.com/global/en/investor-relations.html",
        "notes":   "Quarterly reporting",
    },
    "ABBN": {
        "home":    "https://www.abb.com/global/en",
        "results": "https://global.abb/group/en/investors",
    },
    "ZURN": {
        "home":    "https://www.zurich.com/en/investor-relations",
        "results": "https://www.zurich.com/en/investor-relations/results-and-reports",
        "notes":   "Results and reports",
    },
    "CFR": {
        "home":    "https://www.richemont.com/investor-relations/",
        "results": "https://www.richemont.com/investors/results-reports-presentations/",
    },
    # -----------------------------------------------------------------------
    # Germany
    # -----------------------------------------------------------------------
    "SIE": {
        "home":    "https://www.siemens.com/global/en/company/investor-relations.html",
        "results": "https://www.siemens.com/en-us/company/investor-relations/financial-results/",
    },
    "SAP": {
        "home":    "https://www.sap.com/investor",
        "results": "https://www.sap.com/investors/en.html",
        "notes":   "Financial Documents & Events / Recent Results",
    },
    "ALV": {
        "home":    "https://www.allianz.com/en/investor_relations/",
        "results": "https://www.allianz.com/en/investor_relations.html",
        "notes":   "Results & reports / Group Financial Results",
    },
    "ENR": {
        "home":    "https://www.siemens-energy.com/global/en/home.html",
        "results": "https://www.siemens-energy.com/global/en/home/investor-relations/publications-ad-hoc.html",
    },
    "DTE": {
        "home":    "https://www.telekom.com/en/investor-relations",
        "results": "https://www.telekom.com/en/investor-relations/publications/financial-results",
    },
    "IFX": {
        "home":    "https://www.infineon.com/cms/en/about-infineon/investor/",
        "results": "https://www.infineon.com/about/investor",
    },
    "DBK": {
        "home":    "https://investor-relations.db.com/",
        "results": "https://investor-relations.db.com/reports-and-events/quarterly-results",
    },
    "MUV2": {
        "home":    "https://www.munichre.com/en.html",
        "results": "https://www.munichre.com/en/company/investors/reports-and-presentations/results-reports.html",
    },
    "RHM": {
        "home":    "https://www.rheinmetall.com/en",
        "results": "https://ir.rheinmetall.com/investor-relations/news/financial-reports",
    },
    # -----------------------------------------------------------------------
    # Denmark
    # -----------------------------------------------------------------------
    "NOVO-B": {
        "home":    "https://www.novonordisk.com/investors.html",
        "results": "https://www.novonordisk.com/investors/financial-results.html",
        "notes":   "Financial results / Financial calendar",
    },
    "DSV": {
        "home":    "https://www.dsv.com/en/countries/europe/denmark",
        "results": "https://investor.dsv.com/company-announcements",
    },
    "DANSKE": {
        "home":    "https://www.danskebank.com/ir",
        "results": "https://danskebank.com/ir",
    },
    "VWS": {
        "home":    "https://www.vestas.com/en",
        "results": "https://www.vestas.com/en/investor/reports-and-presentations/vestas-reporting",
    },
    "NZYM-B": {
        "home":    "https://www.novonesis.com/en/investors",
        "results": "https://www.novonesis.com/en/investors/results-and-events",
    },
    "GMAB": {
        "home":    "https://www.genmab.com/",
        "results": "https://ir.genmab.com/financial-reports",
    },
    "MAERSK-B": {
        "home":    "https://www.maersk.com/",
        "results": "https://investor.maersk.com/",
    },
    # -----------------------------------------------------------------------
    # France
    # -----------------------------------------------------------------------
    "SU": {
        "home":    "https://www.se.com/ww/en/about-us/investor-relations/",
        "results": "https://www.se.com/ww/en/about-us/investor-relations/financial-results/",
    },
    "MC": {
        "home":    "https://www.lvmh.com/fr",
        "results": "https://www.lvmh.com/en/financial-calendar",
    },
    "TTE": {
        "home":    "https://totalenergies.com/investors",
        "results": "https://www.lvmh.com/en/financial-calendar",
    },
    "SAF": {
        "home":    "https://www.safran-group.com/",
        "results": "https://www.safran-group.com/finance/publications-results",
    },
    "AIR": {
        "home":    "https://www.airbus.com/en/investors",
        "results": "https://www.airbus.com/en/investors/financial-results",
    },
    "SAN": {
        "home":    "https://www.sanofi.com/en/investors",
        "results": "https://www.sanofi.com/en/investors/reports-and-publications",
    },
    "BNP": {
        "home":    "https://invest.bnpparibas/en",
        "results": "https://invest.bnpparibas/en/results",
    },
    "CS": {
        "home":    "https://www.axa.com/en",
        "results": "https://www.axa.com/en/investor/results",
    },
    # -----------------------------------------------------------------------
    # Taiwan
    # -----------------------------------------------------------------------
    "TSM": {
        "home":    "https://investor.tsmc.com/english",
        "results": "https://investor.tsmc.com/english/quarterly-results",
        "notes":   "Financial Calendar / Quarterly Results / Financial Reports",
    },
    "2317.TW": {
        "home":    "https://www.foxconn.com/zh-tw",
        "results": "https://www.foxconn.com/zh-tw/investor-relations/financial-information/financial-hightlights",
    },
    "2454.TW": {
        "home":    "https://www.mediatek.com/zh-tw/",
        "results": "https://www.mediatek.com/zh-tw/investor-relations/financial-information#quarterly-earnings-release",
    },
    # -----------------------------------------------------------------------
    # South Korea
    # -----------------------------------------------------------------------
    "005930.KS": {
        "home":    "https://www.samsung.com/global/ir/",
        "results": "https://www.samsung.com/global/ir/financial-information/earnings-release/",
        "notes":   "Earnings Releases / Latest quarterly results",
    },
    "000660.KS": {
        "home":    "https://www.skhynix.com/eng/ir/",
        "results": "https://www.skhynix.com/ir/UI-FR-IR01",
    },
    "005380.KS": {
        "home":    "https://www.hyundai.com/worldwide/en/company/ir",
        "results": "https://www.hyundai.com/worldwide/en/company/ir/ir-events",
    },
    "105560.KS": {
        "home":    "https://www.kbfg.com/eng/index.jsp",
        "results": "https://www.kbfg.com/eng/ir/mgt-performance/list.jsp",
    },
    "000270.KS": {
        "home":    "https://www.kia.com/kr?msockid=0cf43b3a70f16ac6292b2e4c711b6b47",
        "results": "https://worldwide.kia.com/int/company/ir/financial/highlights",
    },
    "055550.KS": {
        "home":    "https://www.shinhangroup.com/jp/main",
        "results": "https://www.shinhangroup.com/jp/ir/finance/financialStatements",
    },
    "012450.KS": {
        "home":    "https://www.hanwhaaerospace.com/eng/index.do",
        "results": "https://www.hanwhaaerospace.com/eng/ir/earning-release.do",
    },
    "034020.KS": {
        "home":    "https://www.doosanenerbility.com/en",
        "results": "https://www.doosanenerbility.com/en/investment/ir_data",
    },
    # -----------------------------------------------------------------------
    # China / Hong Kong
    # -----------------------------------------------------------------------
    "0700.HK": {
        "home":    "https://www.tencent.com/en-us/investors.html",
        "results": "https://www.tencent.com/en-us/investors/financial-news.html",
        "notes":   "Financial Releases / Financial Reports",
    },
    "BABA": {
        "home":    "https://www.alibabagroup.com/en-US",
        "results": "https://www.alibabagroup.com/en-US/ir-financial-reports-quarterly-results",
        "notes":   "Quarterly Results / Financial Reports",
    },
    "1810.HK": {
        "home":    "https://www.mi.com/global/",
        "results": "https://ir.mi.com/financial-information/quarterly-results",
    },
    "PDD": {
        "home":    "https://investor.pddholdings.com/",
        "results": "https://investor.pddholdings.com/financial-information/quarterly-results",
    },
    "3690.HK": {
        "home":    "https://www.meituan.com/en-US/about-us",
        "results": "https://www.meituan.com/en-US/investor-relations#quarterly-results",
    },
    "1211.HK": {
        "home":    "https://www.bydglobal.com/en/CompanyIntro.html",
        "results": "https://www.bydglobal.com/en/InvestorAnnals.html?scroll=true",
    },
    "0939.HK": {
        "home":    "https://ccb.com/eng/home/index.shtml",
        "results": "https://ccb.com/eng/investor/performancereports/quarterly_reports/index.shtml",
    },
    "2318.HK": {
        "home":    "https://group.pingan.com/investor_relations.html",
        "results": "https://group.pingan.com/investor_relations/results_and_presentations.html",
    },
    "1398.HK": {
        "home":    "https://www.icbc.com.cn/icbc/en/investor/",
        "results": "https://www.icbc-ltd.com/en/column/1438058343653851171.html",
    },
    "3988.HK": {
        "home":    "https://www.bankofchina.com/en/investor/",
        "results": "https://www.boc.cn/investor/ir3/",
    },
    # -----------------------------------------------------------------------
    # India
    # -----------------------------------------------------------------------
    "HDFCBANK.NS": {
        "home":    "https://www.hdfc.bank.in/",
        "results": "https://www.hdfc.bank.in/about-us/investor-relations?icid=website_organic_nav_aboutus:link:investorrelations",
        "notes":   "Investor Relations / earnings presentation / press release PDFs",
    },
    "RELIANCE.NS": {
        "home":    "https://www.ril.com/",
        "results": "https://www.ril.com/investors/financial-reporting",
        "notes":   "Financial Reporting / Events & Presentations / press releases",
    },
    "ICICIBANK.NS": {
        "home":    "https://www.icicibank.com/about-us/investor",
        "results": "https://www.icici.bank.in/about-us/qfr?ITM=nli_cms_investor_productnavigation_qfr",
        "notes":   "quarterly results archive / latest investor updates",
    },
    "BHARTIARTL.NS": {
        "home":    "https://www.airtel.in/",
        "results": "https://www.airtel.in/about-bharti/equity/results",
    },
    "INFY.NS": {
        "home":    "https://www.infosys.com/investors.html",
        "results": "https://www.infosys.com/investors/reports-filings/quarterly-results.html",
    },
    "AXISBANK.NS": {
        "home":    "https://www.axis.bank.in/",
        "results": "https://www.axis.bank.in/investment",
    },
    "LT.NS": {
        "home":    "https://investors.larsentoubro.com/",
        "results": "https://investors.larsentoubro.com/Quarterly-Results-Archives.aspx",
    },
    "M&M.NS": {
        "home":    "https://www.mahindra.com/investor-relations",
        "results": "https://www.mahindra.com/investor-relations/reports?field_report_category_target_id=7&field_date_value=All&antibot_key=svneiHham6HldybAStPZE6cxgvgme9jBivO1rGkezq8",
    },
    "TCS.NS": {
        "home":    "https://www.tcs.com/investor-relations",
        "results": "https://www.tcs.com/investor-relations",
    },
    "BAJFINANCE.NS": {
        "home":    "https://www.aboutbajajfinserv.com/",
        "results": "https://www.aboutbajajfinserv.com/finance-investor-relations-investor-presentation",
    },
    # -----------------------------------------------------------------------
    # Canada
    # -----------------------------------------------------------------------
    "RY": {
        "home":    "https://www.rbc.com/investor-relations/",
        "results": "https://www.rbc.com/investor-relations/financial-information.html",
    },
    "TD": {
        "home":    "https://www.td.com/ca/en/about-td",
        "results": "https://www.td.com/ca/en/about-td/for-investors/investor-relations/financial-information/financial-reports/quarterly-results",
    },
    "SHOP": {
        "home":    "https://investors.shopify.com/",
        "results": "https://www.shopify.com/investors",
    },
    "AEM": {
        "home":    "https://www.agnicoeagle.com/English/investors/",
        "results": "https://www.agnicoeagle.com/English/investors/financial-information/quarterly-results/",
    },
    "ENB": {
        "home":    "https://www.enbridge.com/",
        "results": "https://www.enbridge.com/investment-center/dashboard",
    },
    "CNQ": {
        "home":    "https://www.cnrl.com/investor-relations/",
        "results": "https://www.cnrl.com/investors/investor-relations/",
    },
    "BAM": {
        "home":    "https://bam.brookfield.com/",
        "results": "https://bam.brookfield.com/reports-sec-filings/quarterly-and-annual-reports",
    },
    # -----------------------------------------------------------------------
    # Australia
    # -----------------------------------------------------------------------
    "BHP.AX": {
        "home":    "https://www.bhp.com/investors",
        "results": "https://www.bhp.com/investors/financial-results-operational-reviews",
    },
    "CBA.AX": {
        "home":    "https://www.commbank.com.au/about-us/investors.html",
        "results": "https://www.commbank.com.au/about-us/investors/results.html",
    },
    "NAB.AX": {
        "home":    "https://www.nab.com.au/",
        "results": "https://www.nab.com.au/about-us/shareholder-centre/financial-disclosures-and-reporting/investor-briefings-and-presentations",
    },
    "WBC.AX": {
        "home":    "https://www.westpac.com.au/about-westpac/investor-centre/",
        "results": "https://www.westpac.com.au/about-westpac/investor-centre/financial-information/results/",
    },
    "ANZ.AX": {
        "home":    "https://www.anz.com.au/personal/",
        "results": "https://www.anz.com/shareholder/centre/reporting/investor-presentations/",
    },
    "MQG.AX": {
        "home":    "https://www.macquarie.com/au/en/investors.html",
        "results": "https://www.macquarie.com/au/en/investors/results.html",
    },
    "CSL.AX": {
        "home":    "https://www.csl.com/investors",
        "results": "https://investors.csl.com/investors/financial-results-and-information",
    },
    "RIO.AX": {
        "home":    "https://www.riotinto.com/en/invest",
        "results": "https://www.riotinto.com/en/invest",
    },
}
