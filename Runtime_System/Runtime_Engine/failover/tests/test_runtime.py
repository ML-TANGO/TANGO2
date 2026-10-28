import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import resolve_container


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.pod = {
            "metadata": {"uid": "pod-uid"},
            "status": {
                "phase": "Running",
                "podIP": "10.0.0.10",
                "containerStatuses": [
                    {
                        "name": "server",
                        "ready": False,
                        "containerID": "containerd://container-id",
                    }
                ],
            },
        }
        self.inspection = {
            "status": {
                "id": "container-id",
                "state": "CONTAINER_RUNNING",
                "labels": {
                    "io.kubernetes.pod.name": "pod-a",
                    "io.kubernetes.pod.namespace": "ns",
                    "io.kubernetes.pod.uid": "pod-uid",
                    "io.kubernetes.container.name": "server",
                },
            },
            "info": {"pid": 123},
        }

    def runner(self, command, **_kwargs):
        payload = self.inspection if command[0] == "crictl" else self.pod
        return SimpleNamespace(stdout=json.dumps(payload))

    def test_not_ready_container_is_rejected_by_default(self):
        with self.assertRaisesRegex(RuntimeError, "not Ready"):
            resolve_container("ns", "pod-a", "server", "config", self.runner)

    @patch("runtime.read_proc_start_ticks", return_value=456)
    def test_campaign_can_resolve_running_but_not_ready_container(self, _ticks):
        target = resolve_container(
            "ns",
            "pod-a",
            "server",
            "config",
            self.runner,
            require_ready=False,
        )
        self.assertEqual(target.container_id, "container-id")
        self.assertEqual(target.pid, 123)
        self.assertEqual(target.start_ticks, 456)


if __name__ == "__main__":
    unittest.main()
