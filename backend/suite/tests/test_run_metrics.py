from django.test import SimpleTestCase

from suite.run_metrics import RECENT_RUN_LIMIT, build_metrics


class RunMetricsTests(SimpleTestCase):
    def test_pass_rate_and_history_share_latest_ten_runs(self):
        records = [
            {
                "passed": index < 6 or index >= RECENT_RUN_LIMIT,
                "run_id": index,
                "suite_name": "回归计划",
                "executor": "tester",
                "finished_at": f"2026-09-{20 - index:02d}T10:00:00+08:00",
            }
            for index in range(12)
        ]

        metric = build_metrics({18: records})[18]

        self.assertEqual(RECENT_RUN_LIMIT, 10)
        self.assertEqual(metric["sample_size"], 10)
        self.assertEqual(metric["passed_count"], 6)
        self.assertEqual(metric["pass_rate"], 60.0)
        self.assertEqual(len(metric["history"]), 10)
        self.assertEqual([item["passed"] for item in metric["history"]], [
            True, True, True, True, True, True, False, False, False, False,
        ])
