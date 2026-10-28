#!/usr/bin/env python3

import os
import signal


def exit_for_cleanup(signum, frame):
    os._exit(0)


if __name__ == "__main__":
    # Probes run through kubectl exec; this PID 1 only keeps the Pod available.
    signal.signal(signal.SIGTERM, exit_for_cleanup)
    print("TC2_CLIENT_IDLE_READY", flush=True)
    while True:
        signal.pause()
