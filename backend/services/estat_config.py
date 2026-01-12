"""
e-Stat Survey Code Configuration
Maps each dataset to its e-Stat survey code for automatic statInfId discovery
"""

# Survey codes for e-Stat Data Catalog API
# Format: {dataset_name: {"survey_code": "...", "file_kind": "...", "description": "..."}}

ESTAT_SURVEY_CONFIGS = {
    "consumer_sentiment": {
        "survey_code": "00100405",  # 消費動向調査
        "stats_code": "000001014549",
        "file_kind": "0",
        "description": "Consumer Trend Survey - Consumer Attitude Index (消費動向調査 - 消費者態度指数)",
        "source_url": "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00100405&tstat=000001014549&cycle=1"
    },
    "retail_sales": {
        "survey_code": "00550030",  # 商業動態統計調査
        "stats_code": "000001081875",  # 小売業販売
        "file_kind": "0",
        "description": "Retail Sales (商業動態統計調査 - 小売業販売)",
        "source_url": "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00550030&tstat=000001081875&cycle=1"
    },
    "scheduled_wage": {
        "survey_code": "00450071",  # 毎月勤労統計調査
        "stats_code": "000001030001",
        "file_kind": "4",
        "description": "Monthly Labour Survey - Scheduled Wage (毎月勤労統計調査 - 所定内給与)",
        "source_url": "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00450071&tstat=000001030001&cycle=1"
    },
    "unemployment": {
        "survey_code": "00200531",  # 労働力調査
        "stats_code": "000000110001",
        "file_kind": "0",
        "description": "Labour Force Survey - Unemployment Rate (労働力調査 - 失業率)",
        "source_url": "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200531&tstat=000000110001&cycle=1"
    }
}


def get_survey_config(dataset_name: str) -> dict:
    """
    Get survey configuration for a dataset

    Args:
        dataset_name: Dataset identifier (e.g., "consumer_sentiment")

    Returns:
        Configuration dictionary

    Raises:
        KeyError: If dataset_name not found
    """
    if dataset_name not in ESTAT_SURVEY_CONFIGS:
        raise KeyError(f"Unknown dataset: {dataset_name}. Available: {list(ESTAT_SURVEY_CONFIGS.keys())}")

    return ESTAT_SURVEY_CONFIGS[dataset_name]
