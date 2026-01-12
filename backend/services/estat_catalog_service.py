"""
e-Stat Data Catalog API Service
Automatically discovers Excel download URLs from e-Stat Data Catalog API

The API returns RESOURCE elements containing direct download URLs for Excel files.
"""
import logging
import os
import re
import requests
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class EStatCatalogService:
    """Service for querying e-Stat Data Catalog API to discover Excel download URLs"""

    BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/getDataCatalog"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize e-Stat Catalog service

        Args:
            api_key: e-Stat API application ID. If None, reads from ESTAT_API_KEY env var
        """
        self.api_key = api_key or os.getenv("ESTAT_API_KEY")
        if not self.api_key:
            logger.warning("ESTAT_API_KEY not found in environment variables")

    def get_excel_download_urls(
        self,
        survey_code: str,
        limit: int = 20,
        data_type: str = "XLS",
        table_name_filter: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get list of Excel download URLs for a given survey

        Args:
            survey_code: Survey code (e.g., "00100405" for consumer sentiment)
            limit: Maximum number of results to return
            data_type: File type filter ("XLS" for Excel files)
            table_name_filter: Optional filter string to match in TABLE_NAME

        Returns:
            List of dicts with 'url', 'title', 'release_date', 'table_name' keys
        """
        if not self.api_key:
            logger.error("Cannot query e-Stat API: No API key configured")
            return []

        try:
            params = {
                "appId": self.api_key,
                "statsCode": survey_code,  # Use statsCode instead of surveyCode
                "dataType": data_type,
                "limit": limit,
                "searchKind": 1  # Search by statsCode
            }

            logger.info(f"Querying e-Stat Data Catalog for survey: {survey_code}")

            response = requests.get(self.BASE_URL, params=params, timeout=60)
            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.content)

            results = []
            catalog_list = root.find(".//DATA_CATALOG_LIST_INF")

            if catalog_list is None:
                logger.warning(f"No data catalog found for survey {survey_code}")
                # Log root element children for debugging
                logger.debug(f"Root element: {root.tag}, children: {[c.tag for c in root]}")
                return []

            # Log number of catalog entries found
            catalog_entries = catalog_list.findall("DATA_CATALOG_INF")
            logger.info(f"Found {len(catalog_entries)} DATA_CATALOG_INF entries")

            # Iterate through DATA_CATALOG_INF elements
            for idx, catalog_inf in enumerate(catalog_entries):
                catalog_id = catalog_inf.get("id", "unknown")

                # Find RESOURCES section - try multiple paths
                # Path 1: Direct under DATA_CATALOG_INF
                resources = catalog_inf.find("RESOURCES")

                # Path 2: Under DATASET
                if resources is None:
                    dataset = catalog_inf.find("DATASET")
                    if dataset is not None:
                        resources = dataset.find("RESOURCES")

                # Path 3: Direct RESOURCE under DATA_CATALOG_INF
                if resources is None:
                    # Check if RESOURCE elements are directly under DATA_CATALOG_INF
                    direct_resources = catalog_inf.findall("RESOURCE")
                    if direct_resources:
                        resources = catalog_inf

                if resources is None:
                    if idx == 0:  # Log structure only for first entry
                        children = [c.tag for c in catalog_inf]
                        logger.debug(f"DATA_CATALOG_INF {catalog_id} children: {children}")
                    continue

                # Iterate through RESOURCE elements
                for resource in resources.findall("RESOURCE"):
                    # Get URL element
                    url_elem = resource.find("URL")
                    format_elem = resource.find("FORMAT")

                    if url_elem is None or url_elem.text is None:
                        continue

                    # Only process XLS format
                    if format_elem is not None and format_elem.text:
                        if not format_elem.text.upper().startswith("XLS"):
                            continue

                    url = url_elem.text.strip()

                    # Get title info
                    title_elem = resource.find("TITLE")
                    table_name = ""
                    if title_elem is not None:
                        table_name_elem = title_elem.find("TABLE_NAME")
                        if table_name_elem is not None and table_name_elem.text:
                            table_name = table_name_elem.text.strip()

                    # Apply table name filter if specified
                    if table_name_filter and table_name_filter not in table_name:
                        continue

                    # Get release date
                    release_date = ""
                    release_date_elem = resource.find("RELEASE_DATE")
                    if release_date_elem is not None and release_date_elem.text:
                        release_date = release_date_elem.text.strip()

                    results.append({
                        "url": url,
                        "table_name": table_name,
                        "release_date": release_date,
                        "format": format_elem.text if format_elem is not None else "XLS"
                    })

            logger.info(f"Found {len(results)} Excel download URLs for survey {survey_code}")

            # Sort by release date descending (most recent first)
            results.sort(key=lambda x: x.get("release_date", ""), reverse=True)

            return results

        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout querying e-Stat Data Catalog API (60s): {e}")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error to e-Stat Data Catalog API: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying e-Stat Data Catalog API: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"Error parsing XML response: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in get_excel_download_urls: {e}")
            return []

    def extract_stat_inf_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract statInfId from e-Stat download URL

        Args:
            url: e-Stat download URL (e.g., https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040396250&...)

        Returns:
            statInfId string or None
        """
        if not url:
            return None

        # Try to find statInfId parameter in URL
        match = re.search(r'statInfId=(\d+)', url)
        if match:
            return match.group(1)

        return None

    def get_latest_stat_inf_ids(
        self,
        survey_code: str,
        limit: int = 20,
        data_type: str = "XLS"
    ) -> List[str]:
        """
        Get list of recent statInfIds for a given survey (legacy method)

        This method extracts statInfId from download URLs.

        Args:
            survey_code: Survey code (e.g., "00550030" for retail sales)
            limit: Maximum number of results to return
            data_type: File type filter ("XLS" for Excel files)

        Returns:
            List of statInfIds, ordered by most recent first
        """
        # Get download URLs
        urls = self.get_excel_download_urls(survey_code, limit, data_type)

        # Extract statInfIds from URLs
        stat_inf_ids = []
        for url_info in urls:
            stat_inf_id = self.extract_stat_inf_id_from_url(url_info.get("url", ""))
            if stat_inf_id and stat_inf_id not in stat_inf_ids:
                stat_inf_ids.append(stat_inf_id)

        logger.info(f"Extracted {len(stat_inf_ids)} statInfIds from URLs for survey {survey_code}")

        return stat_inf_ids

    def get_catalog_metadata(
        self,
        survey_code: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get detailed metadata for catalog entries

        Args:
            survey_code: Survey code (e.g., "00550030" for retail sales)
            limit: Maximum number of results

        Returns:
            List of dictionaries with metadata (id, title, updated_date, etc.)
        """
        if not self.api_key:
            logger.error("Cannot query e-Stat API: No API key configured")
            return []

        try:
            params = {
                "appId": self.api_key,
                "surveyCode": survey_code,
                "dataType": "XLS",
                "limit": limit,
                "searchKind": 2
            }

            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            catalog_list = root.find(".//DATA_CATALOG_LIST_INF")

            if catalog_list is None:
                return []

            results = []

            for catalog_inf in catalog_list.findall("DATA_CATALOG_INF"):
                stat_inf_id = catalog_inf.get("id")
                if not stat_inf_id:
                    continue

                dataset = catalog_inf.find("DATASET")
                if dataset is None:
                    continue

                # Extract metadata
                metadata = {
                    "stat_inf_id": stat_inf_id,
                    "title": self._get_text(dataset, "TITLE"),
                    "stat_name": self._get_text(dataset, "STAT_NAME"),
                    "gov_org": self._get_text(dataset, "GOV_ORG"),
                    "updated_date": self._get_text(dataset, "UPDATED_DATE"),
                    "cycle": self._get_text(dataset, "CYCLE"),
                }

                results.append(metadata)

            logger.info(f"Retrieved metadata for {len(results)} catalog entries")

            return results

        except Exception as e:
            logger.error(f"Error retrieving catalog metadata: {e}")
            return []

    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """
        Safely extract text from XML element

        Args:
            element: Parent XML element
            tag: Tag name to find

        Returns:
            Text content or None
        """
        child = element.find(tag)
        return child.text if child is not None else None


# Singleton instance
_service_instance: Optional[EStatCatalogService] = None


def get_estat_catalog_service() -> EStatCatalogService:
    """Get or create EStatCatalogService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EStatCatalogService()
    return _service_instance
