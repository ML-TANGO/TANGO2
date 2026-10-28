"""Drive the real controller phases with host/container boundaries substituted."""
from contextlib import ExitStack
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service_controller as controller


class Child:
    def __init__(self):
        self.returncode = None
        self.stdout = io.StringIO('')
        self.stderr = io.StringIO('child diagnostics\n')

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


class ManualControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.event = Path(self.temp.name) / 'event'
        self.agent, self.probe = Child(), Child()
        self.phases = []
        self.reject_phase = None
        self.phase_assertions = lambda phase: None
        self.steps = SimpleNamespace(wait=self.wait)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        def replace(name, **kwargs):
            return self.stack.enter_context(patch.object(controller, name, **kwargs))

        self.manual = replace('manual_steps_from_env', return_value=self.steps)
        replace('require_unmodified_scheduling', return_value={})
        replace('verify_service', return_value={
            'spec': {'clusterIP': '10.111.255.250'}, 'metadata': {'name': 'tc2-service', 'uid': 'svc'}})
        replace('run_json', return_value={'metadata': {'uid': 'namespace'}})
        target = SimpleNamespace(pid=42, start_ticks=77, container_id='active-container',
                                 pod_ip='192.0.2.1', to_dict=lambda: {'pid': 42})
        replace('resolve_container', return_value=target)
        replace('apply_endpoint_slice', return_value={})
        replace('wait_for_native_backend')
        replace('wait_for_service_identity', return_value={'valid': True})
        replace('run_pod_probe_convergence', return_value={'valid': True})
        replace('nat_rules', return_value='')
        replace('clear_service_conntrack', return_value={'valid': True})
        replace('ServiceFailoverChain').return_value.dump.return_value = 'test chain\n'
        replace('JsonlWriter')
        replace('AgentLogBuffer', return_value=SimpleNamespace(
            fd=99, persist_attempted=True, close=lambda: None))
        self.stack.enter_context(patch.object(controller.os, 'geteuid', return_value=0))
        self.stack.enter_context(patch.object(controller.os, 'pidfd_open', return_value=123, create=True))
        self.signal = self.stack.enter_context(patch.object(
            controller.signal, 'pidfd_send_signal', create=True))
        self.stack.enter_context(patch.object(controller.os, 'pipe', return_value=(121, 122)))
        self.stack.enter_context(patch.object(controller.os, 'write'))
        self.stack.enter_context(patch.object(controller.os, 'close'))
        self.popen = self.stack.enter_context(patch.object(
            controller.subprocess, 'Popen', side_effect=[self.agent, self.probe]))
        replace('wait_for_agent_event', side_effect=lambda process, event, timeout: {'event': event})

        def probe_ready(process, event, timeout, records):
            row = {'event': 'READY', 'event_id': 'manual-001', 'active_successes': 100}
            records.append(row)
            return row

        replace('read_until_event', side_effect=probe_ready)
        replace('process_matches', return_value=True)
        replace('monotonic_raw_ns', side_effect=[1_000_000, 1_010_000, 30_000_000, 31_000_000])

        def capture(*args):
            self.agent.returncode = self.probe.returncode = 0
            (self.event / 'pod-probe.jsonl').write_text('{"event":"RECOVERED"}\n')
            (self.event / 'pod-probe.stderr.txt').write_text('')
            (self.event / 'agent.jsonl').write_text('raw agent evidence\n')
            return dict(recovered_raw_ns=22_000_000, failures=1, max_probe_gap_us=2000,
                        failure_observations=[dict(started_raw_ns=950_000, observed_raw_ns=2_000_000)])

        replace('collect_agent_logs_after_probe_completion', side_effect=capture)
        records = {
            'FAILOVER_DETECTED': dict(detection_source='active_health_confirmed', detected_raw_ns=3_000_000),
            'ACTIVE_FENCED': dict(fence_execution_confirmed=True, fence_result='task_group_stop_confirmed',
                                 fence_returned_raw_ns=4_000_000),
            'RULE_SWITCH_RETURNED': dict(switch_duration_us=1000),
        }
        replace('read_agent_event', side_effect=lambda path, name: records[name])
        replace('read_agent_exit_state', return_value={'event': 'ACTIVE_EXIT_CONFIRMED'})
        self.calculation = replace('first_post_injection_failure', return_value={
            'started_raw_ns': 950_000, 'observed_raw_ns': 2_000_000})
        replace('application_recovery_valid', return_value=True)
        self.stack.enter_context(patch.object(sys, 'argv', [
            'service_controller.py', '--event-id', 'manual-001', '--kubeconfig', '/unused',
            '--evidence-dir', str(self.event)]))
        self.stack.enter_context(patch('builtins.print'))

    def wait(self, phase, commands, **kwargs):
        self.phases.append((phase, commands))
        self.phase_assertions(phase)
        if phase == self.reject_phase:
            raise RuntimeError('operator phase expired')
        if kwargs.get('guard'):
            kwargs['guard']()
        return commands[0]

    def test_public_phases_own_start_monitor_injection_and_calculation(self):
        def check(phase):
            if phase == 'CREATED':
                self.assertEqual(self.popen.call_count, 0)
            elif phase == 'AGENT_READY':
                self.assertEqual(self.popen.call_count, 1)
            elif phase == 'MONITOR_READY':
                self.assertEqual(self.popen.call_count, 2)
                self.signal.assert_not_called()
            elif phase == 'CAPTURED':
                self.signal.assert_called_once()
                self.calculation.assert_not_called()
                self.assertTrue((self.event / 'pod-probe.jsonl').exists())
                self.assertFalse((self.event / 'summary.json').exists())
            elif phase == 'CALCULATED':
                self.calculation.assert_called_once()
                self.assertEqual(json.loads((self.event / 'summary.json').read_text())['service_outage_us'], 20000)
        self.phase_assertions = check
        self.assertEqual(controller.main(), 0)
        self.assertEqual(self.phases, [('CREATED', ['agent']), ('AGENT_READY', ['monitor']),
                                      ('MONITOR_READY', ['inject']), ('CAPTURED', ['calculate']),
                                      ('CALCULATED', ['reset'])])

    def test_monitor_expiry_keeps_raw_baseline_and_never_injects(self):
        self.reject_phase = 'MONITOR_READY'
        with self.assertRaisesRegex(RuntimeError, 'phase expired'):
            controller.main()
        self.signal.assert_not_called()
        self.calculation.assert_not_called()
        self.assertFalse((self.event / 'summary.json').exists())
        self.assertEqual(json.loads((self.event / 'pod-probe.jsonl').read_text())['event'], 'READY')
        self.assertEqual((self.event / 'pod-probe.stderr.txt').read_text(), 'child diagnostics\n')
        self.assertIn('phase expired', (self.event / 'failure.json').read_text())

    def test_calculation_requires_its_action(self):
        self.reject_phase = 'CAPTURED'
        with self.assertRaisesRegex(RuntimeError, 'phase expired'):
            controller.main()
        self.signal.assert_called_once()
        self.calculation.assert_not_called()
        self.assertFalse((self.event / 'summary.json').exists())

    def test_calculated_event_cannot_return_before_reset_action(self):
        self.reject_phase = 'CALCULATED'
        with self.assertRaisesRegex(RuntimeError, 'phase expired'):
            controller.main()
        self.assertTrue((self.event / 'summary.json').exists())
        self.assertEqual(self.phases[-1], ('CALCULATED', ['reset']))

    def test_legacy_run_has_no_operator_waits(self):
        self.manual.return_value = None
        self.assertEqual(controller.main(), 0)
        self.assertEqual(self.phases, [])
        self.signal.assert_called_once()


class ManualInjectionLeaseTest(unittest.TestCase):
    def test_late_acceptance_or_dead_child_cannot_release_injection(self):
        for dead in (False, True):
            with self.subTest(dead_child=dead):
                agent, probe = Child(), Child()
                if dead:
                    probe.returncode = 0
                steps = Mock()
                with patch.object(controller.time, 'monotonic', side_effect=[100, 101 if dead else 130]):
                    with self.assertRaisesRegex(RuntimeError, 'exited|expired'):
                        controller.wait_for_manual_injection(steps, agent, probe, 'manual-001')
                self.assertEqual(steps.wait.call_args.kwargs['timeout'], 30)


if __name__ == '__main__':
    unittest.main()
