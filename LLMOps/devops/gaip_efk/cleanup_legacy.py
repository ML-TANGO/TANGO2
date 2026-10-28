#!/usr/bin/env python3
"""Move retained records from legacy *-all indices, then remove those indices.

The script is read-only by default. Run --apply only after Fluent Bit writes
dated indices and the retention templates are installed.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone


NAMESPACE = "jonathan-efk"
POD = "elasticsearch-data-0"
# bitnami elasticsearch 파드에 마운트된 클러스터 CA 로 서버 인증서를 검증한다.
ES_CA_CERT = "/opt/bitnami/elasticsearch/config/certs/ca.crt"
RETENTION_DAYS = {
    "thirdparty": 1,
    "jonathan-control-unmarked": 7,
    "jonathan-user": 15,
    "congregate_failed": 1,
    "system-kubecomp": 1,
    "system-kubelet": 1,
    "system-event": 1,
    "jonathan-control": 30,
    "jonathan-control-info": 30,
}
# Fluent Bit 은 control 로그에 임의의 레벨(_cat_level)을 붙인다. 위에 없는 레벨의
# jonathan-control-<level>-all 은 retention_setup.sh 의 control 하위분류 기본값과 같은 30일.
CONTROL_DEFAULT_DAYS = 30


def api(method, path, body=None):
    shell = (
        f'curl -sS --cacert {ES_CA_CERT} -w "\\n%{{http_code}}" '
        '--user "elastic:$(cat "$ELASTICSEARCH_PASSWORD_FILE")" '
        '-H "Content-Type: application/json" -X "$1" '
        '"https://elasticsearch:9200/$2"'
    )
    if body is not None:
        shell += " --data-binary @-"
    cmd = [
        "kubectl", "exec", "-i", "-n", NAMESPACE, POD,
        "--", "sh", "-c", shell, "sh", method, path,
    ]
    result = subprocess.run(
        cmd,
        input=json.dumps(body) if body is not None else "",
        text=True,
        capture_output=True,
        timeout=180,
        check=True,
    )
    payload, status = result.stdout.rsplit("\n", 1)
    if not status.isdigit():
        raise RuntimeError(f"Invalid Elasticsearch response: {result.stdout[:400]}")
    code = int(status)
    if code >= 400 and code != 404:
        raise RuntimeError(f"{method} {path}: HTTP {code}: {payload[:1000]}")
    return code, json.loads(payload) if payload else {}


def legacy_control_prefixes():
    _, response = api("GET", "_cat/indices/jonathan-control-*-all?h=index&format=json")
    if not isinstance(response, list):
        return []
    return sorted(row["index"][: -len("-all")] for row in response)


def exists(index):
    code, _ = api("GET", f"{index}/_settings?filter_path=*.settings.index.provided_name")
    return code == 200


def count(index, cutoff):
    _, response = api(
        "POST", f"{index}/_count",
        {"query": {"range": {"@timestamp": {"gte": cutoff}}}},
    )
    return response["count"]


def dates_including(start, end):
    day = start.date()
    while day <= end.date():
        yield day
        day += timedelta(days=1)


def prepare_indices(prefix, cutoff, now):
    historical = []
    for day in dates_including(cutoff, now):
        index = f"{prefix}-{day:%Y.%m.%d}"
        midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        origination = int(midnight.timestamp() * 1000)
        if exists(index):
            if day < now.date():
                api("PUT", f"{index}/_settings",
                    {"index.lifecycle.origination_date": origination})
        else:
            _, response = api("PUT", index, {
                "settings": {"index.lifecycle.origination_date": origination}
            })
            if not response.get("acknowledged"):
                raise RuntimeError(f"Index creation was not acknowledged: {index}")
        if day < now.date():
            historical.append(index)
    return historical


def reindex(prefix, cutoff, expected):
    old = f"{prefix}-all"
    request = {
        "source": {
            "index": old,
            "size": 5000,
            "query": {"range": {"@timestamp": {"gte": cutoff}}},
        },
        "dest": {"index": f"{prefix}-{datetime.now(timezone.utc):%Y.%m.%d}"},
        "script": {
            "lang": "painless",
            "source": (
                "ctx._index = params.prefix + '-' + "
                "java.time.ZonedDateTime.parse(ctx._source['@timestamp'])"
                ".withZoneSameInstant(java.time.ZoneOffset.UTC)"
                ".format(java.time.format.DateTimeFormatter.ofPattern('yyyy.MM.dd'))"
            ),
            "params": {"prefix": prefix},
        },
    }
    _, started = api("POST", "_reindex?wait_for_completion=false&slices=4", request)
    task_id = started["task"]
    print(f"{old}: reindex task {task_id}, {expected:,} records", flush=True)
    while True:
        _, task = api("GET", f"_tasks/{task_id}")
        if task.get("completed"):
            response = task.get("response", {})
            if "error" in task:
                raise RuntimeError(f"{old}: {task['error']}")
            failures = response.get("failures", [])
            if failures:
                raise RuntimeError(f"{old}: reindex failures: {failures[:2]}")
            moved = response.get("created", 0) + response.get("updated", 0)
            if response.get("total") != expected or moved != expected:
                raise RuntimeError(
                    f"{old}: expected {expected}, total={response.get('total')}, "
                    f"created+updated={moved}"
                )
            print(f"{old}: {moved:,} records copied", flush=True)
            return
        status = task.get("task", {}).get("status", {})
        moved = status.get("created", 0) + status.get("updated", 0)
        print(f"{old}: {moved:,}/{expected:,} copied", flush=True)
        time.sleep(20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Copy retained records and delete legacy indices")
    parser.add_argument("--as-of",
                        help="Freeze the cutoff time, ISO 8601 UTC")
    args = parser.parse_args()
    now = (
        datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        if args.as_of else datetime.now(timezone.utc)
    )
    if now.tzinfo is None:
        parser.error("--as-of requires a timezone")
    now = now.astimezone(timezone.utc)
    targets = dict(RETENTION_DAYS)
    for prefix in legacy_control_prefixes():
        targets.setdefault(prefix, CONTROL_DEFAULT_DAYS)
    for prefix, days in targets.items():
        old = f"{prefix}-all"
        if not exists(old):
            print(f"{old}: absent, skipped", flush=True)
            continue
        cutoff = now - timedelta(days=days)
        cutoff_text = cutoff.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        retained = count(old, cutoff_text)
        print(
            f"{old}: keep {retained:,} records since {cutoff_text}; "
            f"retention {days}d",
            flush=True,
        )
        if not args.apply:
            continue
        if retained:
            historical = prepare_indices(prefix, cutoff, now)
            try:
                for index in historical:
                    api("PUT", f"{index}/_settings",
                        {"index.refresh_interval": "-1"})
                reindex(prefix, cutoff_text, retained)
            finally:
                for index in historical:
                    api("PUT", f"{index}/_settings",
                        {"index.refresh_interval": "1s"})
                if historical:
                    api("POST", f"{','.join(historical)}/_refresh")
            after = count(old, cutoff_text)
            if after != retained:
                raise RuntimeError(
                    f"{old}: source changed during copy ({retained} -> {after}); "
                    "leaving old index in place"
                )
        _, deleted = api("DELETE", old)
        if not deleted.get("acknowledged"):
            raise RuntimeError(f"{old}: deletion was not acknowledged")
        print(f"{old}: deleted", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"Cleanup stopped: {exc}", file=sys.stderr)
        sys.exit(1)
