import copy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_service_configmaps import prepare_configmaps


class ServiceConfigMapsTest(unittest.TestCase):
    def setUp(self):
        self.source = TemporaryDirectory()
        self.addCleanup(self.source.cleanup)
        self.source_dir = Path(self.source.name)
        self.server_data = {"service_server.py": "# server\r\n"}
        self.client_data = {
            "service_client_idle.py": "# client idle\n",
            "service_probe.py": "# probe\n",
            "service_http.py": "# HTTP\n",
            "common.py": "# common\n",
            "scheduling.py": "# scheduling\n",
        }
        for name, content in {**self.server_data, **self.client_data}.items():
            (self.source_dir / name).write_bytes(content.encode("utf-8"))
        self.maps = [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": name,
                    "namespace": "test-tc2",
                },
                "immutable": True,
                "data": data,
            }
            for name, data in [
                ("tc2-service-server", self.server_data),
                ("tc2-service-client", self.client_data),
            ]
        ]

    def reply(self, items):
        return subprocess.CompletedProcess(
            [], 0, json.dumps({"apiVersion": "v1", "kind": "List", "items": items}), ""
        )

    def prepare(self):
        return prepare_configmaps("/test/config", "test-tc2", self.source_dir)

    def test_first_event_creates_exact_immutable_sources_in_one_command(self):
        with patch("prepare_service_configmaps.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "configmaps created\n", ""),
            ]
            self.assertEqual(self.prepare(), [m["metadata"]["name"] for m in self.maps])
        self.assertEqual(len(run.call_args_list), 2)
        query, create = run.call_args_list
        self.assertEqual(
            query.args[0],
            [
                "kubectl", "--kubeconfig", "/test/config", "--namespace", "test-tc2",
                "--request-timeout=30s", "get", "configmap",
                "tc2-service-server", "tc2-service-client", "--ignore-not-found=true",
                "-o", "json",
            ],
        )
        self.assertEqual(create.args[0][-3:], ["create", "-f", "-"])
        self.assertEqual(json.loads(create.kwargs["input"]), {
            "apiVersion": "v1", "kind": "List", "items": self.maps
        })
        self.assertGreater(query.kwargs["timeout"], 0)
        self.assertLessEqual(query.kwargs["timeout"], 65)
        self.assertEqual(create.kwargs["timeout"], query.kwargs["timeout"])
        self.assertTrue(query.kwargs["check"])
        self.assertTrue(create.kwargs["check"])

    def test_later_event_reuses_verified_sources_without_writes(self):
        with patch("prepare_service_configmaps.subprocess.run", return_value=self.reply(self.maps)) as run:
            self.assertEqual(self.prepare(), [])
        run.assert_called_once()

    def test_partial_set_only_creates_missing_map_after_verification(self):
        with patch("prepare_service_configmaps.subprocess.run") as run:
            run.side_effect = [self.reply(self.maps[:1]), self.reply(self.maps[1:])]
            self.assertEqual(self.prepare(), ["tc2-service-client"])
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["items"], self.maps[1:])

    def test_drift_or_invalid_existing_map_prevents_creating_missing_map(self):
        changes = [
            {"data": {"service_server.py": "# stale\n"}},
            {"data": {**self.server_data, "extra.py": "# extra\n"}},
            {"immutable": False},
            {"immutable": 1},
            {"binaryData": {"extra.py": "YQ=="}},
            {"kind": "Secret"},
            {"metadata": {"name": "tc2-service-server", "namespace": "another"}},
            {"metadata": {"name": "unexpected", "namespace": "test-tc2"}},
            {"metadata": {"name": "tc2-service-server", "namespace": "test-tc2", "deletionTimestamp": "2026-01-01T00:00:00Z"}},
        ]
        for change in changes:
            with self.subTest(change=change):
                invalid = {**copy.deepcopy(self.maps[0]), **change}
                with patch("prepare_service_configmaps.subprocess.run", return_value=self.reply([invalid])) as run:
                    with self.assertRaises(RuntimeError):
                        self.prepare()
                run.assert_called_once()

    def test_malformed_or_duplicate_query_result_prevents_writes(self):
        outputs = [
            "not JSON", "[]", "{}",
            json.dumps({"apiVersion": "v1", "kind": "List", "items": None}),
            self.reply([self.maps[0], self.maps[0]]).stdout,
            self.reply([None]).stdout,
        ]
        for output in outputs:
            with self.subTest(output=output):
                reply = subprocess.CompletedProcess([], 0, output, "")
                with patch("prepare_service_configmaps.subprocess.run", return_value=reply) as run:
                    with self.assertRaises(RuntimeError):
                        self.prepare()
                run.assert_called_once()

    def test_api_and_timeout_errors_abort_without_fallback_or_retry(self):
        failures = [
            subprocess.CalledProcessError(1, ["kubectl"], stderr="Forbidden"),
            subprocess.TimeoutExpired(["kubectl"], 65),
        ]
        for failure in failures:
            for creating in (False, True):
                with self.subTest(failure=type(failure).__name__, creating=creating):
                    responses = [self.reply([]), failure] if creating else [failure]
                    with patch("prepare_service_configmaps.subprocess.run", side_effect=responses) as run:
                        with self.assertRaises(RuntimeError):
                            self.prepare()
                    self.assertEqual(run.call_count, len(responses))


if __name__ == "__main__":
    unittest.main()
