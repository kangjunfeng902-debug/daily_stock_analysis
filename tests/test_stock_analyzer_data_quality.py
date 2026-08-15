# -*- coding: utf-8 -*-
"""Data-quality guardrails for StockTrendAnalyzer."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.stock_analyzer import (
    BuySignal,
    MACDStatus,
    RSIStatus,
    StockTrendAnalyzer,
    TrendAnalysisResult,
    VolumeStatus,
)


def _bars(days: int, *, falling_last_day: bool = False, shrinking_last_day: bool = False) -> pd.DataFrame:
    close = np.linspace(10.0, 13.0, days)
    if falling_last_day:
        close[-1] = close[-2] * 0.99
    volume = np.full(days, 1_000_000.0)
    if shrinking_last_day:
        volume[-1] = 500_000.0
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=days, freq="D"),
            "open": close * 0.995,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": volume,
        }
    )


class StockAnalyzerDataQualityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = StockTrendAnalyzer()

    @patch("src.stock_analyzer.get_config")
    def test_20_bars_do_not_award_macd_or_rsi_default_points(self, mock_get_config) -> None:
        mock_get_config.return_value.bias_threshold = 5.0

        result = self.analyzer.analyze(_bars(20), "600519")

        self.assertFalse(result.macd_available)
        self.assertFalse(result.rsi_available)
        self.assertEqual(result.macd_status, MACDStatus.UNAVAILABLE)
        self.assertEqual(result.rsi_status, RSIStatus.UNAVAILABLE)
        self.assertEqual(result.signal_score_max, 75)
        self.assertEqual(result.indicator_coverage_pct, 75)
        self.assertNotIn("MACD 中性", " ".join(result.signal_reasons))
        self.assertEqual(result.buy_signal, BuySignal.WAIT)
        self.assertTrue(any("本项不计分" in risk for risk in result.risk_factors))

    @patch("src.stock_analyzer.get_config")
    def test_25_bars_score_rsi_but_not_macd(self, mock_get_config) -> None:
        mock_get_config.return_value.bias_threshold = 5.0

        result = self.analyzer.analyze(_bars(25), "000001")

        self.assertFalse(result.macd_available)
        self.assertTrue(result.rsi_available)
        self.assertEqual(result.signal_score_max, 85)
        self.assertEqual(result.indicator_coverage_pct, 85)

    @patch("src.stock_analyzer.get_config")
    def test_ma60_is_unavailable_instead_of_reusing_ma20(self, mock_get_config) -> None:
        mock_get_config.return_value.bias_threshold = 5.0

        short = self.analyzer.analyze(_bars(59), "000001")
        complete = self.analyzer.analyze(_bars(60), "000001")

        self.assertFalse(short.ma60_available)
        self.assertEqual(short.ma60, 0.0)
        self.assertTrue(complete.ma60_available)
        self.assertNotEqual(complete.ma60, complete.ma20)

    @patch("src.stock_analyzer.get_config")
    def test_shrinking_pullback_does_not_claim_main_force_intent(self, mock_get_config) -> None:
        mock_get_config.return_value.bias_threshold = 5.0

        result = self.analyzer.analyze(
            _bars(60, falling_last_day=True, shrinking_last_day=True),
            "000001",
        )

        self.assertEqual(result.volume_status, VolumeStatus.SHRINK_VOLUME_DOWN)
        combined = " ".join([result.volume_trend, *result.signal_reasons])
        self.assertNotIn("主力", combined)
        self.assertIn("无法", combined)

    def test_rsi_oversold_language_requires_confirmation(self) -> None:
        df = self.analyzer._calculate_rsi(pd.DataFrame({"close": np.linspace(20.0, 5.0, 30)}))
        result = TrendAnalysisResult(code="000001")

        self.analyzer._analyze_rsi(df, result)

        self.assertEqual(result.rsi_status, RSIStatus.OVERSOLD)
        self.assertNotIn("反弹机会大", result.rsi_signal)
        self.assertIn("不能单独视为反转信号", result.rsi_signal)

    @patch("src.stock_analyzer.get_config")
    def test_rsi_oversold_does_not_receive_maximum_rsi_score(self, mock_get_config) -> None:
        mock_get_config.return_value.bias_threshold = 5.0
        result = TrendAnalysisResult(
            code="000001",
            volume_status=VolumeStatus.NORMAL,
            macd_status=MACDStatus.NEUTRAL,
            macd_available=True,
            rsi_status=RSIStatus.OVERSOLD,
            rsi_available=True,
            rsi_signal="RSI超卖，不能单独视为反转信号",
        )

        self.analyzer._generate_signal(result)

        self.assertTrue(any("不能单独" in risk for risk in result.risk_factors))
        self.assertEqual(result.signal_score, 49)


if __name__ == "__main__":
    unittest.main()
