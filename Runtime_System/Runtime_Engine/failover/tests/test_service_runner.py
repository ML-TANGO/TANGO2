"""Exercise the shell lifecycle without contacting Kubernetes or changing the host."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "run-service-integration.sh"

# Only executable boundaries are replaced. The runner's traps, cleanup gates,
# evidence promotion, and shell error handling execute unchanged.
FAKE_COMMAND = r'''
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

name = Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = Path(os.environ["RUNNER_TEST_STATE"])
state = json.loads(state_path.read_text())

def save():
    state_path.write_text(json.dumps(state))

def action(name):
    state["actions"].append(name)
    save()

if name == "sudo":
    if args[0] == "-n":
        args = args[1:]
    # Model sudo's environment reset at the actual privilege boundary.
    for key in list(os.environ):
        if key.startswith("TANGO2_STEP_"):
            del os.environ[key]
    os.execvp(args[0], args)
elif name == "cat":
    if args == ["/sys/kernel/sched_ext/state"]:
        print("disabled")
    else:
        os.execv("/bin/cat", ["cat", *args])
elif name == "python3":
    script = Path(args[0]).name
    if script == "service_controller.py":
        state["slice"] = True
        state["chain"] = True
        state["controller_env"] = {key: value for key, value in os.environ.items()
                                   if key.startswith("TANGO2_STEP_")}
        action("controller")
        if state["controller"] == "term":
            os.kill(os.getppid(), signal.SIGTERM)
        elif state["controller"] == "fail":
            sys.exit(23)
        elif state["controller"] == "wait_reset":
            while not (state_path.parent / "reset-release").exists():
                time.sleep(.01)
    elif script == "service_chain.py":
        action("delete:chain")
        if state["chain_cleanup_fault"]:
            state["chain_cleanup_fault"] = False
            save()
        else:
            state["chain"] = False
            save()
    elif script == "prepare_service_configmaps.py":
        action("prepare:configmaps")
    else:
        os.execv(os.environ["RUNNER_TEST_PYTHON"], [sys.executable, *args])
elif name == "iptables":
    if (state["chain_query_error"]
            and "delete:chain" in state["actions"]):
        sys.exit(33)
    if args == ["-t", "nat", "-S"]:
        if state["chain"]:
            print("-N TANGO2-TC2-SVC")
        else:
            print("iptables test boundary")
        sys.exit(0)
    if "TANGO2-TC2-SVC" in args:
        sys.exit(0 if state["chain"] else 1)
    print("iptables test boundary")
elif name in ("nvpmodel", "crictl"):
    print(name + " test boundary")
elif name == "sha256sum":
    for path in args:
        print(hashlib.sha256(Path(path).read_bytes()).hexdigest() + "  " + path)
elif name == "kubectl":
    while args and args[0] in ("--kubeconfig", "-n", "--namespace"):
        args = args[2:]
    verb = args[0]
    resource = args[1] if len(args) > 1 else ""
    if verb == "get":
        if resource == state["get_error"]:
            sys.exit(31)
        if (resource == state["cleanup_get_error"]
                and "delete:pod" in state["actions"]):
            sys.exit(32)
        if resource == "namespace":
            if state["namespace"]:
                print("namespace/tango2-tc2-service")
            elif "--ignore-not-found=true" not in args:
                sys.exit(1)
        if resource == "pod":
            for pod in state["pods"]:
                print("pod/" + pod)
        elif resource == "endpointslice":
            if "tc2-service-manual" in args:
                if state["slice"]:
                    print("endpointslice/tc2-service-manual")
                elif "--ignore-not-found=true" not in args:
                    sys.exit(1)
            else:
                print("items: []")
        elif resource == "namespace":
            pass
        else:
            print("test resource snapshot")
    elif verb == "create" and resource == "namespace":
        state["namespace"] = True
        action("create:namespace")
        if state["namespace_create_term"]:
            os.kill(os.getppid(), signal.SIGTERM)
    elif verb == "create" and resource == "configmap":
        print("kind: ConfigMap")
    elif verb == "apply":
        path = args[args.index("-f") + 1]
        if path == "-":
            sys.stdin.read()
        else:
            state["pods"] = ["tc2-service-active", "tc2-service-backup",
                             "tc2-service-client"]
            action("create:pods")
    elif verb == "delete":
        action("delete:" + resource)
        if resource == "namespace":
            if state["namespace_delete_leftover"]:
                state["namespace_delete_leftover"] = False
                save()
                sys.exit(0)
            state["namespace"] = False
            state["pods"] = []
            state["slice"] = False
        elif resource == "pod":
            if state["pod_delete_fault"]:
                fault = state["pod_delete_fault"]
                state["pod_delete_fault"] = ""
                save()
                # Model both an explicit API error and a delete response whose
                # claimed completion is contradicted by the absence check.
                sys.exit(1 if fault == "error" else 0)
            state["pods"] = []
        elif resource == "endpointslice":
            state["slice"] = False
        save()
    elif verb != "wait":
        raise RuntimeError("unexpected kubectl boundary: " + repr(args))
else:
    raise RuntimeError("unexpected executable: " + name)
'''


class ServiceRunnerTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="tc2-runner-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.evidence = self.root / "evidence"
        self.state_path = self.root / "state.json"
        self.state = {
            "namespace": True,
            "pods": [],
            "slice": False,
            "chain": False,
            "controller": "success",
            "pod_delete_fault": "",
            "chain_cleanup_fault": False,
            "chain_query_error": False,
            "namespace_create_term": False,
            "get_error": "",
            "cleanup_get_error": "",
            "namespace_delete_leftover": False,
            "actions": [],
        }
        binaries = self.root / "bin"
        binaries.mkdir()
        executable = binaries / "fake-command"
        executable.write_text("#!" + sys.executable + "\n" + FAKE_COMMAND)
        executable.chmod(0o755)
        for name in ("sudo", "cat", "python3", "iptables", "nvpmodel",
                     "crictl", "kubectl", "sha256sum"):
            (binaries / name).symlink_to(executable)
        kubeconfig = self.root / "kubeconfig"
        kubeconfig.write_text("test boundary only\n")
        self.env = {
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "KUBECONFIG": str(kubeconfig),
            "RUNNER_TEST_STATE": str(self.state_path),
            "RUNNER_TEST_PYTHON": sys.executable,
            "ACCEPT_KPI_FAILURES": "0",
        }

    def run_runner(self, reset_mode="pods"):
        self.state_path.write_text(json.dumps(self.state))
        result = subprocess.run(
            ["/bin/bash", str(RUNNER), str(self.evidence), "runner-test-001",
             "hang", "5", "100", "1", "10", "5", reset_mode],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
            start_new_session=True,
        )
        self.state = json.loads(self.state_path.read_text())
        return result

    def assert_resources_clean(self, namespace=True):
        self.assertEqual(self.state["namespace"], namespace)
        self.assertEqual(self.state["pods"], [])
        self.assertFalse(self.state["slice"])
        self.assertFalse(self.state["chain"])

    def assert_failed_evidence(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("SERVICE_INTEGRATION_COMPLETE", result.stdout)
        self.assertFalse(self.evidence.exists())

    def assert_timing(self, directory, exit_code):
        timing = json.loads((directory / "runner-timing.json").read_text())
        self.assertEqual(timing["event_id"], "runner-test-001")
        self.assertEqual(timing["exit_code"], exit_code)
        self.assertIn(timing["clock"], ("proc_uptime", "monotonic"))
        self.assertGreaterEqual(timing["elapsed_seconds"], 0)
        for phase in timing["phases"]:
            self.assertGreaterEqual(phase["elapsed_seconds"], 0)
        return timing

    def test_success_skips_repeated_cleanup_after_absence_is_verified(self):
        result = self.run_runner()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVICE_INTEGRATION_COMPLETE", result.stdout)
        self.assert_resources_clean()
        actions = self.state["actions"]
        # Eliminating these redundant destructive operations is the explicit
        # optimization contract, while other command ordering remains free.
        for resource in ("pod", "endpointslice", "chain"):
            self.assertEqual(actions.count("delete:" + resource), 1, actions)
        cleanup = (self.evidence / "cleanup.verified.txt").read_text()
        self.assertIn("pod_cleanup=PASS", cleanup)
        self.assertIn("endpointslice_cleanup=PASS", cleanup)
        self.assertIn("chain_cleanup=PASS", cleanup)
        self.assertTrue((self.evidence / "artifacts.sha256").is_file())
        timing = self.assert_timing(self.evidence, 0)
        self.assertIn("controller", [phase["name"] for phase in timing["phases"]])

    def test_full_reset_deletes_owned_namespace(self):
        self.state["namespace"] = False
        result = self.run_runner(reset_mode="full")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_resources_clean(namespace=False)
        self.assertEqual(self.state["actions"].count("delete:namespace"), 1)
        self.assertEqual(self.state["actions"].count("delete:chain"), 1)
        self.assertIn("namespace_cleanup=PASS",
                      (self.evidence / "cleanup.verified.txt").read_text())

    def test_manual_identity_crosses_sudo_environment_reset(self):
        expected = dict(TANGO2_STEP_CONTROL='/private/control',
                        TANGO2_STEP_TARGET='round-02/event-003',
                        TANGO2_STEP_ROUND='round-02')
        self.env.update(expected)
        result = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state['controller_env'], expected)

    def test_outer_cleanup_and_sealing_wait_for_controller_reset_release(self):
        self.state['controller'] = 'wait_reset'
        self.state_path.write_text(json.dumps(self.state))
        process = subprocess.Popen(
            ['/bin/bash', str(RUNNER), str(self.evidence), 'manual-reset-001',
             'hang', '5', '100', '1', '10', '5', 'pods'],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                self.state = json.loads(self.state_path.read_text())
                if 'controller' in self.state['actions']:
                    break
                self.assertIsNone(process.poll())
                time.sleep(.02)
            self.assertIn('controller', self.state['actions'])
            self.assertEqual(len(self.state['pods']), 3)
            self.assertTrue(self.state['chain'])
            self.assertFalse(any(action.startswith('delete:') for action in self.state['actions']))
            self.assertFalse(self.evidence.exists())
            (self.root / 'reset-release').touch()
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.state = json.loads(self.state_path.read_text())
            self.assert_resources_clean()
            self.assertTrue((self.evidence / 'artifacts.sha256').is_file())
        finally:
            (self.root / 'reset-release').touch()
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)

    def test_controller_failure_preserves_exit_and_cleans_owned_resources(self):
        self.state["controller"] = "fail"
        result = self.run_runner()

        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assert_failed_evidence(result)
        self.assert_resources_clean()
        self.assert_timing(Path(str(self.evidence) + ".staging"), 23)

    def test_term_exits_without_resuming_evidence_collection(self):
        self.state["controller"] = "term"
        result = self.run_runner()

        self.assertEqual(result.returncode, 143, result.stdout + result.stderr)
        self.assert_failed_evidence(result)
        self.assert_resources_clean()
        self.assertEqual(self.state["actions"].count("delete:pod"), 1)
        self.assert_timing(Path(str(self.evidence) + ".staging"), 143)

    def test_term_during_namespace_creation_cleans_created_namespace(self):
        self.state.update(namespace=False, namespace_create_term=True)
        result = self.run_runner(reset_mode="full")

        self.assertEqual(result.returncode, 143, result.stdout + result.stderr)
        self.assert_failed_evidence(result)
        self.assert_resources_clean(namespace=False)
        self.assertEqual(self.state["actions"].count("create:namespace"), 1)
        self.assertEqual(self.state["actions"].count("delete:namespace"), 1)

    def test_failed_cleanup_gate_retries_owned_resources_at_exit(self):
        for fault in ("error", "leftover"):
            with self.subTest(fault=fault):
                self.evidence = self.root / ("evidence-" + fault)
                self.state.update(pod_delete_fault=fault, actions=[])
                result = self.run_runner()

                self.assert_failed_evidence(result)
                self.assert_resources_clean()
                self.assertEqual(self.state["actions"].count("delete:pod"), 2)

    def test_full_reset_retains_ownership_until_namespace_absence_is_verified(self):
        self.state.update(namespace=False, namespace_delete_leftover=True)
        result = self.run_runner(reset_mode="full")

        self.assert_failed_evidence(result)
        self.assert_resources_clean(namespace=False)
        self.assertEqual(self.state["actions"].count("delete:namespace"), 2)

    def test_cleanup_query_error_cannot_produce_successful_evidence(self):
        self.state["cleanup_get_error"] = "pod"
        result = self.run_runner()

        self.assertEqual(result.returncode, 32, result.stdout + result.stderr)
        self.assert_failed_evidence(result)
        self.assert_resources_clean()

    def test_chain_cleanup_and_query_failures_cannot_publish_evidence(self):
        self.state.update(chain=True, chain_cleanup_fault=True,
                          chain_query_error=True)
        result = self.run_runner()

        self.assertEqual(result.returncode, 33, result.stdout + result.stderr)
        self.assert_failed_evidence(result)
        self.assert_resources_clean()
        self.assertEqual(self.state["actions"].count("delete:chain"), 2)

    def test_chain_left_in_successful_readback_retries_cleanup_at_exit(self):
        self.state.update(chain=True, chain_cleanup_fault=True)
        result = self.run_runner()

        self.assert_failed_evidence(result)
        self.assert_resources_clean()
        self.assertEqual(self.state["actions"].count("delete:chain"), 2)

    def test_entry_refusal_does_not_delete_preexisting_resources(self):
        for obstruction in ("namespace", "pods", "slice"):
            with self.subTest(obstruction=obstruction):
                self.state.update(namespace=True, pods=[], slice=False,
                                  chain=True, actions=[])
                reset_mode = "pods"
                if obstruction == "namespace":
                    reset_mode = "full"
                elif obstruction == "pods":
                    self.state["pods"] = ["someone-elses-pod"]
                else:
                    self.state["slice"] = True
                before = dict(self.state)
                result = self.run_runner(reset_mode=reset_mode)

                self.assert_failed_evidence(result)
                self.assertEqual(self.state, before)

    def test_failed_entry_queries_cannot_authorize_resource_reuse(self):
        for resource in ("namespace", "pod", "endpointslice"):
            with self.subTest(resource=resource):
                self.state.update(get_error=resource, chain=True, actions=[])
                before = dict(self.state)
                result = self.run_runner()

                self.assertEqual(result.returncode, 31,
                                 result.stdout + result.stderr)
                self.assert_failed_evidence(result)
                self.assertEqual(self.state, before)


if __name__ == "__main__":
    unittest.main()
