"""
ルールベース粗い分類
"""

import re

# カテゴリごとのキーワードパターン（大文字小文字区別なし）
_RULES = [
    ("central_bank", [
        r"\bFed\b", r"\bFOMC\b", r"\bPowell\b", r"\bWaller\b", r"\bBowman\b",
        r"\bLogan\b", r"\bBarkin\b", r"\bBostic\b", r"\bDaly\b", r"\bGoolsbee\b",
        r"\bHarker\b", r"\bKashkari\b", r"\bMester\b", r"\bWilliams\b",
        r"\bECB\b", r"\bLagarde\b", r"\bPanetta\b", r"\bSimkus\b", r"\bLane\b",
        r"\bBOJ\b", r"\bUeda\b", r"\bKuroda\b",
        r"\bBOE\b", r"\bBailey\b",
        r"\bRBA\b", r"\bRBNZ\b", r"\bSNB\b", r"\bBOC\b", r"\bPBOC\b",
        r"\bcentral bank\b", r"\brate hike\b", r"\brate cut\b",
        r"\binterest rate\b", r"\bmonetary policy\b",
    ]),
    ("macro", [
        r"\bCPI\b", r"\bPPI\b", r"\bNFP\b", r"\bpayrolls?\b", r"\bGDP\b",
        r"\bISM\b", r"\bPMI\b", r"\bPCE\b", r"\bRetail Sales\b",
        r"\bUnemployment\b", r"\bJobless Claims\b", r"\bJOLTS\b",
        r"\bDurable Goods\b", r"\bTrade Balance\b", r"\bHousing Starts\b",
        r"\bConsumer Confidence\b", r"\bNFIB\b", r"\bADP\b",
        r"\bIndustrial Production\b", r"\bCapacity Utilization\b",
        r"\bIMF\b", r"\$MACRO\b",
    ]),
    ("oil_energy", [
        r"\bOPEC\b", r"\bcrude\b", r"\bbarrel\b", r"\boil\b",
        r"\brefinery\b", r"\benergy\b", r"\bnatural gas\b", r"\bEIA\b",
        r"\bBrent\b", r"\bWTI\b", r"\bpetroleum\b", r"\bHormuz\b",
    ]),
    ("geopolitics", [
        r"\btariff\b", r"\bwar\b", r"\bsanctions?\b", r"\bmissile\b",
        r"\bstrike\b", r"\bmilitary\b", r"\bNATO\b", r"\bIran\b",
        r"\bRussia\b", r"\bUkraine\b", r"\bChina\b", r"\bTaiwan\b",
        r"\bNorth Korea\b", r"\bgeopoliti\w+\b",
    ]),
    ("equities", [
        r"\bS&P\s*500\b", r"\bNasdaq\b", r"\bDow\b", r"\bNikkei\b",
        r"\bTesla\b", r"\bApple\b", r"\bNVIDIA\b", r"\bMag\s*7\b",
        r"\bearnings\b", r"\bdeliveries\b", r"\bIPO\b",
        r"\bMOO Imbalance\b",
    ]),
    ("rates_fx", [
        r"\bTreasury\b", r"\byield\b", r"\bspread\b", r"\bOAT\b",
        r"\bSOFR\b", r"\bSONIA\b", r"\bBund\b", r"\bJGB\b",
        r"\bEUR/USD\b", r"\bUSD/JPY\b", r"\bGBP/USD\b",
        r"\bDXY\b", r"\bfed funds rate\b", r"\bbill auction\b",
        r"\bBid-to-Cover\b",
    ]),
]

# コンパイル済みパターン
_COMPILED_RULES = [
    (cat, [re.compile(p, re.IGNORECASE) for p in patterns])
    for cat, patterns in _RULES
]

# 発言者抽出パターン
_SPEAKER_PATTERNS = [
    re.compile(r"(?:Fed'?s|ECB'?s|BOJ'?s|BOE'?s|RBA'?s)\s+(\w+)", re.IGNORECASE),
    re.compile(r"(\w+(?:'s)?)\s+(?:President|Governor|Chair|Secretary|Minister|Ambassador)", re.IGNORECASE),
]

_ORG_PATTERNS = [
    re.compile(r"\b(IMF|Goldman\s+Sachs|JPMorgan|BofA|ING|MUFG|Kremlin|OPEC\+?)\b", re.IGNORECASE),
]


def classify(text: str) -> str:
    """テキストを粗いカテゴリに分類"""
    if not text:
        return "other"
    for cat, patterns in _COMPILED_RULES:
        for p in patterns:
            if p.search(text):
                return cat
    return "other"


def extract_speaker(text: str) -> str | None:
    """発言者名を抽出"""
    if not text:
        return None
    for p in _SPEAKER_PATTERNS:
        m = p.search(text)
        if m:
            return m.group(1)
    return None


def extract_organization(text: str) -> str | None:
    """組織名を抽出"""
    if not text:
        return None
    for p in _ORG_PATTERNS:
        m = p.search(text)
        if m:
            return m.group(1)
    return None
