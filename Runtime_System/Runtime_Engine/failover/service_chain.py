#!/usr/bin/env python3

import argparse
import ipaddress
import subprocess

from chain import CHAIN_RE
from prepared_restore import PreparedRestore


class ServiceFailoverChain:
    def __init__(
        self,
        chain="TANGO2-TC2-SVC",
        service_ip="10.111.255.250",
        service_port=18080,
        node_ip="10.2.58.155",
        node_port=30082,
        runner=subprocess.run,
    ):
        if not CHAIN_RE.fullmatch(chain):
            raise ValueError(f"invalid chain name: {chain}")
        self.chain = chain
        self.service_ip = str(ipaddress.ip_address(service_ip))
        self.service_port = self._port(service_port)
        self.node_ip = str(ipaddress.ip_address(node_ip))
        self.node_port = self._port(node_port)
        self.runner = runner

    @staticmethod
    def _port(value):
        port = int(value)
        if not 1 <= port <= 65535:
            raise ValueError(f"invalid port: {value}")
        return port

    def _run(self, command, check=True, input_text=None):
        return self.runner(
            command,
            check=check,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _entry_specs(self):
        return (
            ("OUTPUT", "cluster-output", self.service_ip, self.service_port),
            (
                "PREROUTING",
                "cluster-prerouting",
                self.service_ip,
                self.service_port,
            ),
            ("OUTPUT", "node-output", self.node_ip, self.node_port),
            (
                "PREROUTING",
                "node-prerouting",
                self.node_ip,
                self.node_port,
            ),
        )

    def _entry_args(self, label, address, port):
        return [
            "-p",
            "tcp",
            "-d",
            f"{address}/32",
            "-m",
            "tcp",
            "--dport",
            str(port),
            "-m",
            "comment",
            "--comment",
            f"tango2 tc2 svc {label}",
            "-j",
            self.chain,
        ]

    def target_rule(self, target_ip, target_port):
        target_ip = str(ipaddress.ip_address(target_ip))
        target_port = self._port(target_port)
        return (
            f'-A {self.chain} -p tcp -m comment '
            f'--comment "tango2 tc2 svc target" -j DNAT '
            f"--to-destination {target_ip}:{target_port}"
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

    def prepare_target(self, target_ip, target_port):
        return PreparedRestore(self.restore_payload(target_ip, target_port))

    def setup(self, target_ip, target_port):
        existing = self._run(
            ["iptables", "-w", "1", "-t", "nat", "-S", self.chain],
            check=False,
        )
        if existing.returncode == 0:
            raise RuntimeError(f"chain {self.chain} already exists")
        try:
            self._run(["iptables", "-w", "1", "-t", "nat", "-N", self.chain])
            self.apply_target(target_ip, target_port)
            for builtin, label, address, port in self._entry_specs():
                self._run(
                    [
                        "iptables",
                        "-w",
                        "1",
                        "-t",
                        "nat",
                        "-I",
                        builtin,
                        "1",
                    ]
                    + self._entry_args(label, address, port)
                )
            self.verify_entries()
            self.verify_target(target_ip, target_port)
        except Exception:
            self.cleanup()
            raise

    def cleanup(self):
        for builtin, label, address, port in self._entry_specs():
            delete = [
                "iptables",
                "-w",
                "1",
                "-t",
                "nat",
                "-D",
                builtin,
            ] + self._entry_args(label, address, port)
            while self._run(delete, check=False).returncode == 0:
                pass
        self._run(
            ["iptables", "-w", "1", "-t", "nat", "-F", self.chain],
            check=False,
        )
        self._run(
            ["iptables", "-w", "1", "-t", "nat", "-X", self.chain],
            check=False,
        )

    def verify_entries(self):
        for builtin, label, address, port in self._entry_specs():
            completed = self._run(
                [
                    "iptables",
                    "-w",
                    "1",
                    "-t",
                    "nat",
                    "-C",
                    builtin,
                ]
                + self._entry_args(label, address, port),
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"missing owned {builtin} entry {label}")

    def dump(self):
        return self._run(
            ["iptables", "-w", "1", "-t", "nat", "-S", self.chain]
        ).stdout

    def verify_target(self, target_ip, target_port):
        expected = self.target_rule(target_ip, target_port)
        actual = [
            line.strip()
            for line in self.dump().splitlines()
            if line.startswith("-A ")
        ]
        if actual != [expected]:
            raise RuntimeError(
                f"service target mismatch: actual={actual!r} "
                f"expected={[expected]!r}"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("cleanup", "dump"))
    parser.add_argument("--chain", default="TANGO2-TC2-SVC")
    parser.add_argument("--service-ip", default="10.111.255.250")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument("--node-ip", default="10.2.58.155")
    parser.add_argument("--node-port", type=int, default=30082)
    args = parser.parse_args()
    chain = ServiceFailoverChain(
        args.chain,
        args.service_ip,
        args.service_port,
        args.node_ip,
        args.node_port,
    )
    if args.action == "cleanup":
        chain.cleanup()
    else:
        print(chain.dump(), end="")


if __name__ == "__main__":
    main()
