"""Edge 가상 디바이스 e2e 드라이버 — 등록→토큰→configure→heartbeat→deploy→refresh→검증.

in-cluster 파드에서 실행(예: kubectl exec -i <pod> -- python3 < edge_e2e_driver.py).
admin 엣지 API는 Kong 우회 서비스 직접호출 + 헤더 jf-user:admin (s2s). stdlib 만 사용.
스펙: docs/superpowers/specs/2026-07-21-edge-virtual-device-e2e-design.md
"""
import json
import os
import time
import urllib.request
import urllib.error

RES = os.environ.get("RES_BASE", "http://jfb-app-resource-svc.jonathan-system.svc.cluster.local")
VDEV = os.environ.get("VDEV_BASE", "http://jfb-edge-virtual-device.jonathan-system.svc.cluster.local:8500")
ADMIN = {"jf-user": "admin", "Content-Type": "application/json"}


def http(method, url, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, str(e)


def result_of(payload):
    return payload.get("result", payload) if isinstance(payload, dict) else payload


def main():
    name = "vdev-e2e-" + time.strftime("%Y%m%d-%H%M%S")
    print("== 1) register worker ==")
    st, body = http("POST", f"{RES}/api/edge/workers", ADMIN, {"name": name, "remote_manager_url": VDEV})
    print(st, json.dumps(body, ensure_ascii=False)[:400])
    r = result_of(body)
    worker_id = r.get("id") or r.get("worker_id")
    device_id = r.get("device_id")
    assert worker_id and device_id, "register 실패 (id/device_id 없음)"
    print(f"   -> worker_id={worker_id} device_id={device_id}")

    print("== 2) issue token ==")
    st, body = http("POST", f"{RES}/api/edge/workers/{worker_id}/token", ADMIN)
    print(st, json.dumps(body, ensure_ascii=False)[:300])
    token = result_of(body).get("token")
    assert token, "token 발급 실패"

    print("== 3) configure harness (heartbeat 시작) ==")
    hb_url = f"{RES}/api/edge/devices/{device_id}/heartbeat"
    st, body = http("POST", f"{VDEV}/configure", {"Content-Type": "application/json"},
                    {"device_id": device_id, "token": token, "heartbeat_url": hb_url})
    print(st, json.dumps(body, ensure_ascii=False)[:200])

    print("== 4) wait heartbeat -> conn_status ==")
    time.sleep(6)
    st, body = http("GET", f"{RES}/api/edge/workers/{worker_id}", ADMIN)
    conn = result_of(body).get("conn_status")
    print(f"   conn_status={conn}")

    print("== 5) deploy (=> mock /ops) ==")
    st, body = http("POST", f"{RES}/api/edge/workers/{worker_id}/deploy", ADMIN,
                    {"image": "acrylaaai/llm_deployment_llamacpp:dev",
                     "model_name": "vdev-model", "model_version": "1",
                     "gguf_path": "models/vdev.gguf"})
    print(st, json.dumps(body, ensure_ascii=False)[:400])
    ds1 = result_of(body).get("deploy_state")

    print("== 6) refresh (=> mock /metrics) ==")
    st, body = http("POST", f"{RES}/api/edge/workers/{worker_id}/refresh", ADMIN)
    print(st, json.dumps(body, ensure_ascii=False)[:300])

    print("== 7) verify ==")
    st, body = http("GET", f"{RES}/api/edge/workers/{worker_id}", ADMIN)
    w = result_of(body)
    conn = w.get("conn_status")
    ds = w.get("deploy_state")
    dm = w.get("deploy_model")
    print(f"   conn_status={conn} deploy_state={ds} deploy_model={dm} deploy_state(after /ops)={ds1}")
    ok = (conn == "online") and (ds in ("running", "deploying"))
    print("RESULT:", "PASS" if ok else "FAIL", f"(worker_id={worker_id}, device_id={device_id})")


if __name__ == "__main__":
    main()
