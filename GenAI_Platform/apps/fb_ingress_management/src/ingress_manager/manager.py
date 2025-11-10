from utils import settings
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

def manager_routine():
    global _manager_routine_running
    
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