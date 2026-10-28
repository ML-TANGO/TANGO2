#!/usr/bin/env python3
"""Prepare immutable workload source ConfigMaps without accepting stale code."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


SOURCE_FILES = {
    "tc2-service-server": ("service_server.py",),
    "tc2-service-client": (
        "service_client_idle.py", "service_probe.py", "service_http.py",
        "common.py", "scheduling.py"
    ),
}


def prepare_configmaps(kubeconfig, namespace, source_dir):
    desired = {
        name: {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": namespace},
            "immutable": True,
            "data": {
                filename: (Path(source_dir) / filename).read_bytes().decode("utf-8")
                for filename in filenames
            },
        }
        for name, filenames in SOURCE_FILES.items()
    }
    command = [
        "kubectl", "--kubeconfig", str(kubeconfig), "--namespace", namespace,
        "--request-timeout=30s",
    ]

    def kubectl(*args, manifest=None):
        try:
            return subprocess.run(
                [*command, *args],
                input=None if manifest is None else json.dumps(manifest),
                text=True,
                capture_output=True,
                check=True,
                # Named resources may require two sequential API requests.
                timeout=65,
            ).stdout
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            raise RuntimeError(f"ConfigMap {args[0]} failed: {detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"ConfigMap {args[0]} timed out") from exc

    output = kubectl(
        "get", "configmap", *desired, "--ignore-not-found=true", "-o", "json"
    )
    try:
        # kubectl emits no JSON when every named object is absent and ignored.
        result = json.loads(output) if output.strip() else {
            "apiVersion": "v1", "kind": "List", "items": []
        }
    except json.JSONDecodeError as exc:
        raise RuntimeError("ConfigMap query returned invalid JSON") from exc
    if (
        not isinstance(result, dict)
        or result.get("apiVersion") != "v1"
        or result.get("kind") != "List"
        or not isinstance(result.get("items"), list)
    ):
        raise RuntimeError("ConfigMap query did not return a resource List")

    existing = set()
    for item in result["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("metadata"), dict):
            raise RuntimeError("ConfigMap query returned an invalid resource")
        metadata = item["metadata"]
        name = metadata.get("name")
        if not isinstance(name, str) or name not in desired or name in existing:
            raise RuntimeError("ConfigMap query returned unexpected or duplicate names")
        if (
            item.get("apiVersion") != "v1"
            or item.get("kind") != "ConfigMap"
            or metadata.get("namespace") != namespace
            or metadata.get("deletionTimestamp") is not None
            or item.get("immutable") is not True
            or item.get("data") != desired[name]["data"]
            or item.get("binaryData") not in (None, {})
        ):
            raise RuntimeError(
                f"ConfigMap {name} does not match immutable workload sources; "
                "refusing to reuse or overwrite it"
            )
        existing.add(name)

    # Validate every returned object before creating any missing object.
    missing = [name for name in desired if name not in existing]
    if missing:
        kubectl("create", "-f", "-", manifest={
            "apiVersion": "v1",
            "kind": "List",
            "items": [desired[name] for name in missing],
        })
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        created = prepare_configmaps(args.kubeconfig, args.namespace, args.source_dir)
    except (RuntimeError, OSError, UnicodeError) as exc:
        print(f"ConfigMap preparation failed: {exc}", file=sys.stderr)
        return 1
    print(f"ConfigMaps ready: created={len(created)} reused={len(SOURCE_FILES) - len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
