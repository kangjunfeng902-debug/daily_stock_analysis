# -*- coding: utf-8 -*-
"""Static checks for intelligence-source mappings in the daily workflow."""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github/workflows/00-daily-analysis.yml"


def test_daily_analysis_maps_news_intelligence_settings_without_enabling_by_default() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for key in (
        "NEWS_INTEL_AUTO_FETCH_ENABLED",
        "NEWS_INTEL_RETENTION_DAYS",
        "NEWS_INTEL_FETCH_TIMEOUT_SEC",
        "NEWS_INTEL_MAX_ITEMS_PER_SOURCE",
        "NEWSNOW_BASE_URL",
    ):
        assert f"{key}: ${{{{ vars.{key} || secrets.{key} }}}}" in workflow

    assert "NEWS_INTEL_AUTO_FETCH_ENABLED: true" not in workflow
    assert "本地资讯池自动刷新: ✅ 已启用" in workflow
