#!/usr/bin/env python3
"""
FOMC Projections API Router
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from datetime import datetime, date
from typing import List, Dict
import calendar

try:
    from backend.services.usa.fomc_projections_service import FOMCProjectionsService
    from backend.services.usa.fomc_table1_service import FOMCTable1Service
    from backend.services.usa.fomc_schedule_service import FOMCScheduleService
except ImportError:
    from services.usa.fomc_projections_service import FOMCProjectionsService
    from services.usa.fomc_table1_service import FOMCTable1Service
    from services.usa.fomc_schedule_service import FOMCScheduleService

router = APIRouter(prefix="/api/fomc-projections", tags=["fomc-projections"])
service = FOMCProjectionsService()
table1_service = FOMCTable1Service()
schedule_service = FOMCScheduleService()


@router.get("/sep-dates")
def get_sep_dates(count: int = 4):
    """
    過去のFOMC SEP発表日を取得（FRB公式スケジュールから）

    Args:
        count: 取得する日付の数（デフォルト: 4）

    Returns:
        日付リスト
    """
    try:
        dates = schedule_service.get_sep_dates(count)
        return {
            "dates": dates,
            "count": len(dates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming-sep-dates")
def get_upcoming_sep_dates(count: int = 4):
    """
    今後のFOMC SEP発表日を取得

    Args:
        count: 取得する日付の数（デフォルト: 4）

    Returns:
        日付リスト（近い順）
    """
    try:
        dates = schedule_service.get_upcoming_sep_dates(count)
        return {
            "dates": dates,
            "count": len(dates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
def get_fomc_schedule():
    """
    全てのFOMCスケジュールを取得

    Returns:
        年ごとのスケジュール
    """
    try:
        schedule = schedule_service.get_schedule()
        return {
            "schedule": schedule,
            "source": "Federal Reserve"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/update")
def update_fomc_schedule():
    """
    FOMCスケジュールキャッシュを強制的に更新

    Returns:
        更新結果
    """
    try:
        success = schedule_service.update_cache()
        return {
            "success": success,
            "message": "Schedule cache updated" if success else "Failed to update cache"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/figure2/{date}")
def get_fomc_projections_figure2(date: str):
    """
    指定された日付のFOMC Projections Figure 2を取得

    Args:
        date: FOMC発表日 (YYYYMMDD形式)

    Returns:
        PNG画像
    """
    try:
        # 日付をパース
        release_date = datetime.strptime(date, "%Y%m%d")

        # まずキャッシュをチェック
        cached_data = service.get_cached_figure_2(release_date)

        if cached_data:
            return Response(content=cached_data, media_type="image/png")

        # キャッシュにない場合、PDFから取得を試みる
        try:
            image_data = service.get_or_update_figure_2(release_date)

            if image_data:
                return Response(content=image_data, media_type="image/png")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"データがありません。{date[:4]}年{date[4:6]}月{date[6:8]}日のFOMC Projectionsはまだ公開されていません。"
                )
        except Exception as e:
            # PDFからの取得に失敗した場合
            raise HTTPException(
                status_code=404,
                detail=f"データがありません。{date[:4]}年{date[4:6]}月{date[6:8]}日のFOMC Projectionsの取得に失敗しました: {str(e)}"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/{date}")
def update_fomc_projections(date: str):
    """
    指定された日付のFOMC Projections Figure 2を強制的に更新

    Args:
        date: FOMC発表日 (YYYYMMDD形式)

    Returns:
        更新結果
    """
    try:
        # 日付をパース
        release_date = datetime.strptime(date, "%Y%m%d")

        # Figure 2を更新
        result = service.update_figure_2(release_date)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest")
def get_latest_fomc_projections():
    """
    最新のFOMC Projections Figure 2を取得

    Returns:
        PNG画像
    """
    try:
        # キャッシュディレクトリから最新のファイルを探す
        cache_dir = service.CACHE_DIR

        # figure2_で始まるPNGファイルを全て取得
        png_files = sorted(cache_dir.glob("figure2_*.png"), reverse=True)

        if png_files:
            # キャッシュがある場合は最新のファイルを返す
            latest_file = png_files[0]

            with open(latest_file, 'rb') as f:
                image_data = f.read()

            return Response(content=image_data, media_type="image/png")
        else:
            # キャッシュがない場合は、デフォルトの最新日付（2025年9月17日）からPDFを取得
            default_date = datetime.strptime("20250917", "%Y%m%d")

            try:
                # PDFから取得を試みる
                image_data = service.get_or_update_figure_2(default_date)

                if image_data:
                    return Response(content=image_data, media_type="image/png")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="データがありません。FOMC Projectionsはまだ公開されていません。"
                    )
            except Exception as e:
                # PDFからの取得に失敗した場合
                raise HTTPException(
                    status_code=404,
                    detail=f"データがありません。FOMC Projections (2025年9月17日) の取得に失敗しました: {str(e)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table1/latest")
def get_latest_fomc_table1():
    """
    最新のFOMC Economic Projections Table 1を取得

    Returns:
        PNG画像
    """
    try:
        # 最新のTable 1を取得
        image_data = table1_service.get_latest_table_1()

        if image_data:
            return Response(content=image_data, media_type="image/png")
        else:
            # キャッシュがない場合は、デフォルトの最新日付（2025年9月17日）からPDFを取得
            default_date = datetime.strptime("20250917", "%Y%m%d")

            try:
                result = table1_service.update_table_1(default_date)

                if result["success"]:
                    image_data = table1_service.get_cached_table_1(default_date)
                    if image_data:
                        return Response(content=image_data, media_type="image/png")

                raise HTTPException(
                    status_code=404,
                    detail="データがありません。FOMC Economic Projectionsはまだ公開されていません。"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"データがありません。FOMC Economic Projections (2025年9月17日) の取得に失敗しました: {str(e)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table1/{date}")
def get_fomc_table1(date: str):
    """
    指定された日付のFOMC Economic Projections Table 1を取得

    Args:
        date: FOMC発表日 (YYYYMMDD形式)

    Returns:
        PNG画像
    """
    try:
        # 日付をパース
        release_date = datetime.strptime(date, "%Y%m%d")

        # まずキャッシュをチェック
        cached_data = table1_service.get_cached_table_1(release_date)

        if cached_data:
            return Response(content=cached_data, media_type="image/png")

        # キャッシュにない場合、PDFから取得を試みる
        try:
            result = table1_service.update_table_1(release_date)

            if result["success"]:
                image_data = table1_service.get_cached_table_1(release_date)
                if image_data:
                    return Response(content=image_data, media_type="image/png")

            raise HTTPException(
                status_code=404,
                detail=f"データがありません。{date[:4]}年{date[4:6]}月{date[6:8]}日のFOMC Economic Projectionsはまだ公開されていません。"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"データがありません。{date[:4]}年{date[4:6]}月{date[6:8]}日のFOMC Economic Projectionsの取得に失敗しました: {str(e)}"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
