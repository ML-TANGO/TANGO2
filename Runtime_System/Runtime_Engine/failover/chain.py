#!/usr/bin/env python3

import argparse
import ipaddress
import re
import subprocess


CHAIN_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,27}$")


class FailoverChain:
    def __init__(
        self,
        chain="TANGO2-TC2",
        entry_ip="10.111.255.250",
        entry_port=18080,
        runner=subprocess.run,
    ):
        if not CHAIN_RE.fullmatch(chain):
            raise ValueError(f"invalid chain name: {chain}")
        self.chain = chain
        self.entry_ip = str(ipaddress.ip_address(entry_ip))
        self.entry_port = self._port(entry_port)
        self.runner = runner

    @staticmethod
    def _port(value):
        port = int(value)
        if not 1 <= port <= 65535:
            raise ValueError(f"invalid port: {value}")
        return port

    def _entry_args(self):
        return [
            "-p",
            "tcp",
            "-d",
            f"{self.entry_ip}/32",
            "--dport",
            str(self.entry_port),
            "-m",
            "comment",
            "--comment",
            "tango2 tc2 entry",
            "-j",
            self.chain,
        ]

    def _run(self, command, check=True, input_text=None):
        return self.runner(
            command,
            check=check,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def setup(self, target_ip, target_port):
        existing = self._run(
            ["iptables", "-w", "1", "-t", "nat", "-S", self.chain],
            check=False,
        )
        if existing.returncode == 0:
            raise RuntimeError(f"chain {self.chain} already exists")
        self._run(["iptables", "-w", "1", "-t", "nat", "-N", self.chain])
        self.switch_target(target_ip, target_port)
        self._run(
            ["iptables", "-w", "1", "-t", "nat", "-I", "OUTPUT", "1"]
            + self._entry_args()
        )

    def cleanup(self):
        delete = ["iptables", "-w", "1", "-t", "nat", "-D", "OUTPUT"]
        while self._run(delete + self._entry_args(), check=False).returncode == 0:
            pass
        self._run(
            ["iptables", "-w", "1", "-t", "nat", "-F", self.chain],
            check=False,
        )
        self._run(
            ["iptables", "-w", "1", "-t", "nat", "-X", self.chain],
            check=False,
        )

    def target_rule(self, target_ip, target_port):
        target_ip = str(ipaddress.ip_address(target_ip))
        target_port = self._port(target_port)
        return (
            f'-A {self.chain} -p tcp -m comment --comment "tango2 tc2 target" '
            f"-j DNAT --to-destination {target_ip}:{target_port}"
        )

    def restore_payload(self, target_ip, target_port):
        return (
            "*nat\n"
            f"-F {self.chain}\n"
            f"{self.target_rule(target_ip, target_port)}\n"
            "COMMIT\n"
        )

    def apply_target(self, target_ip, target_port):
        self._run(
            ["iptables-restore", "--wait", "1", "--noflush"],
            input_text=self.restore_payload(target_ip, target_port),
        )

    def switch_target(self, target_ip, target_port):
        self.apply_target(target_ip, target_port)
        self.verify_target(target_ip, target_port)

    def dump(self):
        completed = self._run(
            ["iptables", "-w", "1", "-t", "nat", "-S", self.chain]
        )
        return completed.stdout

    def verify_target(self, target_ip, target_port):
        expected = self.target_rule(target_ip, target_port)
        actual = [line.strip() for line in self.dump().splitlines() if line.startswith("-A ")]
        if actual != [expected]:
            raise RuntimeError(
                f"chain target mismatch: actual={actual!r} expected={expected!r}"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("cleanup", "dump"))
    parser.add_argument("--chain", default="TANGO2-TC2")
    parser.add_argument("--entry-ip", default="10.111.255.250")
    parser.add_argument("--entry-port", type=int, default=18080)
    args = parser.parse_args()
    chain = FailoverChain(args.chain, args.entry_ip, args.entry_port)
    if args.action == "cleanup":
        chain.cleanup()
    else:
        print(chain.dump(), end="")


if __name__ == "__main__":
    main()
