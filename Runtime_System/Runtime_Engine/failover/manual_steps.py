#!/usr/bin/env python3
"""Explicit operator checkpoints outside the measured critical sections.

Mutable control files live outside evidence. A consumed request is acknowledged
only at the next completed checkpoint, including across event controllers.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import uuid


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def atomic(path, value):
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        with temporary.open('x') as output:
            json.dump(value, output, indent=2)
            output.write('\n')
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read(path):
    return json.loads(path.read_text())


@contextmanager
def lock(directory):
    fd = os.open(directory / 'submit.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        yield


class ManualSteps:
    def __init__(self, directory):
        self.directory = Path(directory)
        stat = self.directory.lstat()
        if self.directory.is_symlink() or stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
            raise RuntimeError('step control must be private and owned by this user')
        self.identity = read(self.directory / 'identity.json')
        self.validate_boot()
        status = self.directory / 'status.json'
        self.current_target = os.environ.get('TANGO2_STEP_TARGET') or (
            read(status).get('target', '') if status.exists() else '')

    @classmethod
    def from_env(cls):
        directory = os.environ.get('TANGO2_STEP_CONTROL')
        return cls(directory) if directory else None

    def validate_boot(self):
        if self.identity['boot_id'] != boot_id():
            raise RuntimeError('board rebooted; this session cannot be resumed')

    def target(self, value):
        self.current_target = value

    def _ack(self, status, error=None):
        pending = self.directory / 'pending.json'
        if pending.exists():
            request = read(pending)
            atomic(self.directory / 'receipts' / (request['id'] + '.json'),
                   dict(request=request, status=status, error=error))
            pending.unlink()

    def finish(self, phase='DONE', details=None):
        with lock(self.directory):
            old = read(self.directory / 'status.json') if (self.directory / 'status.json').exists() else {}
            status = dict(session=self.identity['session'], boot_id=self.identity['boot_id'],
                          target=self.current_target, phase=phase, commands=[],
                          sequence=old.get('sequence', 0) + 1, controller_pid=os.getpid(),
                          details=details or {})
            self._ack(status, None if phase == 'DONE' else str(details or phase))
            atomic(self.directory / 'status.json', status)
            # A cancellation can race with a submitted but unconsumed request.
            request_path = self.directory / 'request.json'
            if request_path.exists():
                request = read(request_path)
                atomic(self.directory / 'receipts' / (request['id'] + '.json'),
                       dict(request=request, status=status, error='session ended before action'))
                request_path.unlink()

    def wait(self, phase, commands, *, timeout=1800, guard=None, details=None):
        self.validate_boot()
        with lock(self.directory):
            old = read(self.directory / 'status.json') if (self.directory / 'status.json').exists() else {}
            status = dict(session=self.identity['session'], boot_id=self.identity['boot_id'],
                          target=self.current_target, phase=phase, commands=list(commands),
                          sequence=old.get('sequence', 0) + 1, controller_pid=os.getpid(),
                          details=details or {})
            self._ack(status)
            atomic(self.directory / 'status.json', status)
        deadline = time.monotonic() + timeout
        while True:
            self.validate_boot()
            if guard is not None:
                guard()
            if time.monotonic() >= deadline:
                raise RuntimeError(f'operator step lease expired: {phase}')
            with lock(self.directory):
                path = self.directory / 'request.json'
                if path.exists():
                    request = read(path)
                    valid = all(request.get(key) == status[key] for key in
                                ('session', 'boot_id', 'target', 'phase', 'sequence'))
                    valid = valid and request.get('command') in commands
                    if not valid:
                        atomic(self.directory / 'receipts' / (request['id'] + '.json'),
                               dict(request=request, status=status, error='stale or wrong-phase request'))
                        path.unlink()
                    else:
                        atomic(self.directory / 'pending.json', request)
                        path.unlink()
                        atomic(self.directory / 'status.json',
                               dict(status, phase='RUNNING', commands=[], action=request['command']))
                        return request['command']
            time.sleep(0.025)

    def submit(self, command, request_id=None):
        self.validate_boot()
        request_id = request_id or uuid.uuid4().hex
        if not request_id.isalnum() or len(request_id) > 64:
            raise ValueError('invalid request ID')
        with lock(self.directory):
            receipt = self.directory / 'receipts' / (request_id + '.json')
            if receipt.exists():
                previous = read(receipt)
                if previous['request']['command'] != command:
                    raise RuntimeError('request ID reused for a different action')
                return request_id
            status = read(self.directory / 'status.json')
            if command not in status['commands']:
                raise RuntimeError(f"{command} is unavailable at {status['target']} {status['phase']}")
            for name in ('request.json', 'pending.json'):
                if (self.directory / name).exists():
                    raise RuntimeError('another step is pending; inspect status')
            request = {key: status[key] for key in
                       ('session', 'boot_id', 'target', 'phase', 'sequence')}
            request.update(id=request_id, command=command)
            atomic(self.directory / 'request.json', request)
        return request_id


if __name__ == '__main__':
    steps = ManualSteps.from_env()
    if steps is None or len(sys.argv) < 4 or sys.argv[1] != 'wait':
        raise SystemExit('usage: manual_steps.py wait PHASE COMMAND... (manual environment required)')
    steps.wait(sys.argv[2], sys.argv[3:])
