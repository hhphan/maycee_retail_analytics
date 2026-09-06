from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
APP_DIR = REPO_ROOT / "app"
WORKSPACE_FREE_DATA = (
    REPO_ROOT.parents[1]
    / "repos"
    / "maycee_retail_dataset"
    / "v1.0"
    / "output"
    / "huggingface"
    / "free_v1_0"
)
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(APP_DIR))

from check_public_boundary import run_checks
from data import FREE_END, FREE_START, build_metric_frames, load_free_tier_tables
from fetch_free_data import DEFAULT_REPO_ID, planned_patterns


class PublicBoundaryTests(unittest.TestCase):
    def test_repository_passes_public_boundary_check(self) -> None:
        self.assertEqual(run_checks(), [])

    def test_free_fetch_is_limited_to_public_dataset_tables(self) -> None:
        self.assertEqual(DEFAULT_REPO_ID, "SDataPro/maycee-retail-dataset")
        self.assertEqual(planned_patterns(["transactions"]), ["data/transactions/*"])

    def test_personal_app_has_no_restricted_adapter_or_key_handling(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in APP_DIR.glob("*.py"))
        self.assertNotIn("MAYCEE_LICENCE_KEY", source)
        self.assertNotIn("MAYCEE_LICENSE_KEY", source)
        self.assertNotIn("load_dashboard_tables", source)

    @unittest.skipUnless(WORKSPACE_FREE_DATA.exists(), "local public/free Maycee export not available")
    def test_real_public_data_metrics_and_dates(self) -> None:
        tables = load_free_tier_tables(WORKSPACE_FREE_DATA)
        metrics = build_metric_frames(tables)
        dates = tables["transactions"]["transaction_date"]
        self.assertEqual(dates.min().date().isoformat(), FREE_START)
        self.assertEqual(dates.max().date().isoformat(), FREE_END)
        self.assertEqual(len(tables["transactions"]), 164_968)
        self.assertEqual(len(tables["items"]), 420_016)
        self.assertEqual(len(tables["returns"]), 8_762)
        self.assertAlmostEqual(float(metrics["kpis"].iloc[0]["revenue"]), 120_708_096.68, places=2)

    @unittest.skipUnless(WORKSPACE_FREE_DATA.exists(), "local public/free Maycee export not available")
    def test_streamlit_dashboard_runs(self) -> None:
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"MAYCEE_FREE_DATA_DIR": str(WORKSPACE_FREE_DATA)}):
            app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=120).run()
        self.assertEqual(app.exception, [])


if __name__ == "__main__":
    unittest.main()
