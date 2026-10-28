import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('manual_steps', Path(__file__).parents[1] / 'manual_steps.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class StepProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        (self.directory / 'receipts').mkdir()
        module.atomic(self.directory / 'identity.json', dict(session='session-A', boot_id='boot-A'))
        self.boot = patch.object(module, 'boot_id', return_value='boot-A')
        self.boot.start()
        self.addCleanup(self.boot.stop)
        self.addCleanup(self.temp.cleanup)
        self.steps = module.ManualSteps(self.directory)
        self.steps.target('round-01/event-001')

    def await_phase(self, phase):
        for _ in range(100):
            if (self.directory / 'status.json').exists():
                if module.read(self.directory / 'status.json')['phase'] == phase:
                    return
            time.sleep(.01)
        self.fail('checkpoint not announced')

    def test_receipt_waits_for_work_and_reset_next_controller(self):
        released = threading.Event()
        def worker():
            self.assertEqual(self.steps.wait('CREATED', ['agent'], timeout=2), 'agent')
            released.wait(2)
            self.steps.wait('AGENT_READY', ['reset'], timeout=2)
        thread = threading.Thread(target=worker)
        thread.start()
        self.await_phase('CREATED')
        request = self.steps.submit('agent', 'one')
        self.await_phase('RUNNING')
        self.assertFalse((self.directory / 'receipts' / 'one.json').exists())
        released.set()
        self.await_phase('AGENT_READY')
        self.assertIsNone(module.read(self.directory / 'receipts' / 'one.json')['error'])
        self.assertEqual(self.steps.submit('agent', request), request)
        self.steps.submit('reset', 'two')
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertFalse((self.directory / 'receipts' / 'two.json').exists())
        next_controller = module.ManualSteps(self.directory)
        next_controller.finish('DONE')
        self.assertIsNone(module.read(self.directory / 'receipts' / 'two.json')['error'])

    def test_wrong_phase_and_expired_lease_never_inject(self):
        errors = []
        def worker():
            try:
                self.steps.wait('MONITOR_READY', ['inject'], timeout=.15)
            except RuntimeError as error:
                errors.append(str(error))
        thread = threading.Thread(target=worker)
        thread.start()
        self.await_phase('MONITOR_READY')
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            self.steps.submit('reset')
        status = module.read(self.directory / 'status.json')
        module.atomic(self.directory / 'request.json',
                      dict(status, command='inject', id='stale', sequence=0))
        thread.join(2)
        self.assertIn('expired', errors[0])
        self.assertIn('stale', module.read(self.directory / 'receipts' / 'stale.json')['error'])
        self.assertFalse((self.directory / 'pending.json').exists())

    def test_reboot_rejects_continuation(self):
        with patch.object(module, 'boot_id', return_value='boot-B'):
            with self.assertRaisesRegex(RuntimeError, 'rebooted'):
                self.steps.submit('inject')

    def test_child_guard_failure_prevents_action(self):
        def failed_child():
            raise RuntimeError('probe exited')
        with self.assertRaisesRegex(RuntimeError, 'probe exited'):
            self.steps.wait('MONITOR_READY', ['inject'], guard=failed_child)
        self.assertFalse((self.directory / 'pending.json').exists())


if __name__ == '__main__':
    unittest.main()
