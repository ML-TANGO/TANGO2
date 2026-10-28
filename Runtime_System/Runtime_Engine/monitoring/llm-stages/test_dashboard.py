import json
import pathlib
import unittest

import dashboard


def flattened(panels):
    for panel in panels:
        yield panel
        yield from flattened(panel.get("panels", []))


class DashboardContract(unittest.TestCase):
    def test_required_metrics_and_run_annotation_are_provisioned(self):
        provisioned = json.loads(pathlib.Path(__file__).with_name("grafana-dashboard.json").read_text())
        panels = list(flattened(provisioned["panels"]))
        expressions = [target["expr"] for panel in panels for target in panel.get("targets", [])]
        joined = "\n".join(expressions)
        self.assertIn("tango2_llm_window_output_tokens", joined)
        self.assertIn("tango2_llm_window_rate", joined)
        self.assertIn("tango2_llm_window_duration_seconds", joined)
        self.assertIn("tango2_llm_window_samples", joined)
        self.assertNotIn("histogram_quantile", joined)
        self.assertNotIn("$mode", joined)
        self.assertEqual([v["name"] for v in provisioned["templating"]["list"]], ["case"])
        self.assertIn("tango2_llm_run_info", joined)
        for expression in expressions:
            if "tango2_llm_window_" in expression:
                self.assertIn('mode="detail"', expression)
        sample_panel = next(panel for panel in panels if panel["title"] == "Eligible samples · last 5m")
        self.assertEqual(sample_panel["type"], "table")
        self.assertIn("Fewer than 30 samples for a metric", sample_panel["description"])
        generated = [target["expr"] for panel in flattened(dashboard.dashboard["panels"])
                     for target in panel.get("targets", [])]
        self.assertEqual(expressions, generated)
        annotation = provisioned["annotations"]["list"][0]
        self.assertIn("tango2_llm_run_boundary_timestamp_seconds", annotation["target"]["expr"])
        self.assertEqual(annotation["titleFormat"], "{{run_id}} {{event}}")

    def test_gpu_phases_are_instant_comparisons_and_trends_keep_real_gaps(self):
        panels = dashboard.dashboard["panels"]
        for title in ("Prefill · host and GPU", "Decode · generation and GPU",
                      "GPU prefill · compare all cases", "GPU decode · compare all cases"):
            panel = next(panel for panel in panels if panel["title"] == title)
            self.assertEqual(panel["type"], "bargauge")
            self.assertTrue(all(target["instant"] and not target["range"] for target in panel["targets"]))
            self.assertEqual(panel["fieldConfig"]["defaults"]["min"], 0)
        trends = [panel for panel in panels if panel["type"] == "timeseries"]
        self.assertTrue(trends)
        for panel in trends:
            style = panel["fieldConfig"]["defaults"]["custom"]
            self.assertEqual(style["lineInterpolation"], "linear")
            self.assertFalse(style["spanNulls"])
            self.assertEqual(style["showPoints"], "never")
        diagnostics = next(panel for panel in panels if panel["title"] == "Runtime diagnostics")
        self.assertTrue(diagnostics["collapsed"])
        self.assertNotIn("Host stages (overlaps kept separate)", [panel["title"] for panel in panels])

    def test_cpu_panels_keep_thread_scope_and_unavailable_values_explicit(self):
        panels = list(flattened(dashboard.dashboard["panels"]))
        cpu = [item for item in panels if item["title"] in (
            "CPU execution · instrumented threads", "Runnable CPU wait · instrumented threads")]
        self.assertEqual(len(cpu), 2)
        for item in cpu:
            self.assertEqual(item["type"], "bargauge")
            self.assertIn("helper threads are outside scope", item["description"])
            self.assertIn("not first-to-last token generation", item["description"])
            self.assertTrue(all("tango2_llm_cpu_window_seconds" in target["expr"]
                                and 'mode="detail"' in target["expr"]
                                and " or " not in target["expr"] for target in item["targets"]))
        self.assertTrue(any(item["title"] == "CPU eligible samples · last 5m" for item in panels))


if __name__ == "__main__":
    unittest.main()
