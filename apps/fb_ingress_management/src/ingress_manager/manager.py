from utils import settings
from utils import kong_helper, deployment_api  # 게시(D6) orphan sweep
from utils.msa_db import db_deployment          # 게시(D6) orphan sweep
import traceback, time, sys, threading
import logging
from ingress_manager.admin_api import *
# from kubernetes import config, client

# config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH) # 추후 kubectl 필요할 경우 대비
# coreV1Api = client.CoreV1Api()   
MANAGER_LOOP_INTERVAL = 5

# 중복 실행 방지를 위한 글로벌 플래그
_manager_routine_running = False
_manager_routine_lock = threading.Lock()

class ThreadingLock:
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, t, v, tb):
        self.lock.release()
        if tb is not None:
            traceback.print_exception(t, v, tb)
        return True

jf_tlock = ThreadingLock(threading.Lock())

def debug_log(message):
    """디버그 모드일 때만 로그 출력 (admin_api의 DEBUG_MODE 참조)"""
    from ingress_manager.admin_api import DEBUG_MODE
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr)

# ── 게시(D6) orphan sweep ─────────────────────────────────────────────
# deployment_api row 가 전혀 없는 Kong 게시 route(ext-dep-<id>) + 그 dep-<id> consumer/key 를 정리.
# teardown 부분실패·Kong 완전 outage·out-of-band 배포삭제로 남은 dangling 크리덴셜 안전망(3b-2 후속).
# 5s 메인 루프 안에서 ORPHAN_SWEEP_INTERVAL 마다만 실행(throttle).
#
# 안전 설계(3-way 리뷰 BLOCK 반영):
#  - **route(ext-dep-*) 기준 앵커**: route 는 D6 publish 만 생성하므로, 우연히 'dep-123' 이름의
#    실제 유저 consumer 를 orphan 으로 오삭제할 위험이 없다(consumer 열거 안 함). exploit 가능한
#    잔여(=키+route 공존)는 route 앵커로 모두 커버; route 없는 consumer-only 잔여는 비악용성.
#  - **정상 기준 = row 존재(enabled 무관)**: 중지-보존(enabled=0, consumer/key 유지) 를 보존.
#  - **삭제 직전 row 재확인**(TOCTOU): 스윕 도중 publish 가 row 를 썼으면 보존.
#  - **grace**: route created_at 이 grace 이내면 갓 게시(진행중)로 보고 skip. created_at 누락 시 now.
ORPHAN_SWEEP_INTERVAL = 120  # sec
ORPHAN_GRACE_SEC = 60        # sec
_last_orphan_sweep = 0.0


def _orphan_dep_id(name, prefix):
    """name 이 '<prefix><digits>' 면 int deployment_id, 아니면 None. ascii 숫자만(‘²’ 등 isdigit
    True 지만 int() 크래시하는 유니코드 숫자 배제 — 한 개가 전체 스윕을 죽이지 않도록)."""
    if name and name.startswith(prefix):
        tail = name[len(prefix):]
        if tail.isascii() and tail.isdigit():
            return int(tail)
    return None


def kong_sweep_orphan_publish():
    """게시(D6) orphan sweep. deployment_api row 없는 ext-dep-<id> route → 공용 teardown(멱등)."""
    all_ids = db_deployment.list_deployment_api_ids()
    if all_ids is None:
        # DB 조회 실패 → 반드시 스킵(빈 집합 오인 시 유효 게시를 전부 삭제하므로).
        print("[orphan-sweep] skip: deployment_api 조회 실패", file=sys.stderr)
        return
    known = set(all_ids)  # row 존재(enabled 무관) = 정상
    now = time.time()
    try:
        routes = kong_helper.list_routes()
    except Exception:
        traceback.print_exc()
        return  # Kong 열거 실패 → 스킵(부분 목록으로 유효 게시 오판 방지)
    candidates = {}  # dep_id -> 관측된 최신 created_at(여럿이면 max = 보호적)
    for r in routes:
        did = _orphan_dep_id(r.get("name"), "ext-dep-")
        if did is None or did in known:
            continue
        created = r.get("created_at") or now  # 누락 시 now → grace 로 보호(즉시 삭제 방지)
        candidates[did] = max(candidates.get(did, 0), created)
    swept, grace, raced, unconfirmed = [], [], [], []
    for did, created in candidates.items():
        if now - created < ORPHAN_GRACE_SEC:
            grace.append(did)  # 갓 게시(publish 진행중) 보호
            continue
        # 삭제 직전(후보별) 최신 집합 재조회 — check-then-act 간극 최소화. 루프 진입 전 배치 스냅샷은
        # 뒤 후보일수록 stale 해져, 앞 후보 teardown(느린 Kong 호출) 동안 재게시된 정상 배포를 오삭제할
        # 수 있다. 단건 get_deployment_api 는 '부재'와 'DB 오류'가 둘 다 None 이라 못 씀 → list 재조회로
        # 구분(None=조회 실패 → 이 후보 보류하고 다음 주기 재시도 / set 이면 그 안에 있으면 보존).
        fresh = db_deployment.list_deployment_api_ids()
        if fresh is None:
            unconfirmed.append(did)  # DB blip: 부재로 오인 말고 이번 주기엔 건드리지 않음
            continue
        if did in set(fresh):  # 스윕 도중 재게시됐거나 여전히 존재 → 보존(raced)
            raced.append(did)
            continue
        failed = False
        try:
            deployment_api.teardown_deployment_api(did)  # 멱등: route + dep-{id} consumer/key + row
        except Exception:
            failed = True
            traceback.print_exc()  # 부분 실패는 다음 주기 재시도
        try:
            # 대부분의 단일 배포에는 이 service가 없지만 404 멱등 삭제이므로 기존 정리를 방해하지 않는다.
            # 앞 정리가 실패해도 독립 시도해 이중 게시의 합성 service가 계속 orphan으로 남지 않게 한다.
            deployment_api.teardown_composite_service(did)
        except Exception:
            failed = True
            traceback.print_exc()  # Kong 일시 오류는 다음 주기 재시도
        if not failed:
            swept.append(did)
    if swept or grace or raced or unconfirmed:
        print("[orphan-sweep] swept=%s grace-skipped=%s raced-skipped=%s unconfirmed=%s" % (
            swept, grace, raced, unconfirmed), file=sys.stderr)


def manager_routine():
    global _manager_routine_running, _last_orphan_sweep
    
    # 중복 실행 방지 체크
    with _manager_routine_lock:
        if _manager_routine_running:
            print(f"[MANAGER] ⚠️  Manager routine already running! Skipping duplicate execution.", file=sys.stderr)
            return
        _manager_routine_running = True
    
    try:
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        from ingress_manager.admin_api import DEBUG_MODE, ACL_ENABLED, ALLOW_ALL_ROUTES
        print(f"[MANAGER] 🚀 Starting ingress management routine (DEBUG_MODE: {DEBUG_MODE})", file=sys.stderr)
        
        # 🔥 앱 시작 시 한 번만 실행: 설정 동기화
        print(f"[MANAGER] 📋 Current settings: ACL_ENABLED={ACL_ENABLED}, ALLOW_ALL_ROUTES={ALLOW_ALL_ROUTES}", file=sys.stderr)
        print(f"[MANAGER] 🔄 Performing initial Kong configuration sync...", file=sys.stderr)
        
        try:
            from ingress_manager.admin_api import kong_initialize_on_startup
            kong_initialize_on_startup()
            print(f"[MANAGER] ✅ Initial configuration sync completed", file=sys.stderr)
        except Exception as init_error:
            print(f"[MANAGER] ❌ Initial configuration sync failed: {init_error}", file=sys.stderr)
            import traceback
            traceback.print_exc()
    
        while True:
            try:
                time.sleep(MANAGER_LOOP_INTERVAL)
                
                # 1. Kong 헬스 체크
                if kong_health_check():
                    debug_log("Kong health check: OK")
                    
                    # 2. Consumer 체크 (DB 비교)
                    debug_log("Step 1: Syncing users to consumers...")
                    kong_sync_user_to_consumer()

                    # 3. Consumer ACL 그룹 동기화 (가장 중요한 단계 - 워크스페이스 변경 반영)
                    debug_log("Step 2: Syncing consumer ACL groups (workspace & project permissions)...")
                    kong_sync_consumer_acl_groups()

                    # 4. Plugin 체크
                    debug_log("Step 3: Checking plugins...")
                    kong_check_plugin()

                    # 5. Routes 관리
                    debug_log("Step 4: Checking routes...")
                    kong_check_routes()

                    # 6. 자동 ACL 적용 (tool pod ingress routes에 ACL 적용)
                    debug_log("Step 5: Auto-applying ACL to routes...")
                    kong_auto_apply_acl_to_routes()
                    
                    # 6b. 게시(D6) orphan sweep (throttle: ORPHAN_SWEEP_INTERVAL 마다만)
                    if time.monotonic() - _last_orphan_sweep >= ORPHAN_SWEEP_INTERVAL:
                        debug_log("Step 6: Orphan publish sweep...")
                        kong_sweep_orphan_publish()
                        _last_orphan_sweep = time.monotonic()

                    # 7. 현황 요약 출력 (항상 표시)
                    print(f"[MANAGER] ═══════════════════════════════════════════════════════════", file=sys.stderr)
                    display_ingress_status_summary()
                    print(f"[MANAGER] ═══════════════════════════════════════════════════════════", file=sys.stderr)
                    
                    debug_log("Routine cycle completed successfully")
                else:
                    print(f"[MANAGER] Kong health check: FAILED", file=sys.stderr)
                    raise Exception("Kong is not reachable.")
                
            except Exception as e:
                print(f"[MANAGER] Error in routine cycle: {e}", file=sys.stderr)
                from ingress_manager.admin_api import DEBUG_MODE
                if DEBUG_MODE:
                    print(traceback.print_exc(), file=sys.stderr)
                    
    except KeyboardInterrupt:
        print(f"[MANAGER] Manager routine interrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"[MANAGER] Fatal error in manager routine: {e}", file=sys.stderr)
    finally:
        # 종료 시 플래그 리셋
        with _manager_routine_lock:
            _manager_routine_running = False
        print(f"[MANAGER] Manager routine stopped", file=sys.stderr)
