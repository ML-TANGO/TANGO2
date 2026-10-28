import subprocess
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service_chain import ServiceFailoverChain


class RecordingRunner:
    def __init__(self, dump=""):
        self.calls = []
        self.dump = dump

    def __call__(
        self,
        command,
        check,
        input,
        stdout,
        stderr,
        text,
    ):
        self.calls.append((command, input))
        output = (
            self.dump
            if command[-2:] == ["-S", "TANGO2-TC2-SVC"]
            else ""
        )
        return subprocess.CompletedProcess(command, 0, output, "")


class ServiceChainTest(unittest.TestCase):
    def test_restore_payload_replaces_only_owned_target(self):
        chain = ServiceFailoverChain()
        payload = chain.restore_payload("172.20.1.3", 8080)
        self.assertIn("-F TANGO2-TC2-SVC", payload)
        self.assertIn("--to-destination 172.20.1.3:8080", payload)
        self.assertNotIn("KUBE-", payload)

    def test_target_switch_uses_noflush(self):
        expected = (
            '-A TANGO2-TC2-SVC -p tcp -m comment --comment '
            '"tango2 tc2 svc target" -j DNAT '
            "--to-destination 172.20.1.3:8080\n"
        )
        runner = RecordingRunner(expected)
        chain = ServiceFailoverChain(runner=runner)
        chain.apply_target("172.20.1.3", 8080)
        self.assertEqual(
            runner.calls[0][0],
            ["iptables-restore", "--wait", "1", "--noflush"],
        )

    def test_entry_specs_cover_service_and_nodeport_paths(self):
        chain = ServiceFailoverChain()
        self.assertEqual(
            {spec[0] for spec in chain._entry_specs()},
            {"OUTPUT", "PREROUTING"},
        )
        self.assertEqual(len(chain._entry_specs()), 4)

    def test_invalid_values_fail_closed(self):
        with self.assertRaises(ValueError):
            ServiceFailoverChain("lowercase")
        with self.assertRaises(ValueError):
            ServiceFailoverChain(node_port=70000)


if __name__ == "__main__":
    unittest.main()
