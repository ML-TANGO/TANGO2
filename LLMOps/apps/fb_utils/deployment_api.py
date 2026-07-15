"""게시(D6) 외부 API — 공용 상수 / 식별자 / teardown(취소) core.

fb_deployment(publish/unpublish 의 소유권 wrapper)와 llm_playground(stop/delete
lifecycle)가 **같은 Kong 리소스 네이밍과 정리 로직**을 쓰도록 단일 정의한다.
분기(divergence)를 막는 게 목적 — 예전엔 이 상수/헬퍼가 fb_deployment/service.py 안에만
있어 llm_playground lifecycle 이 게시물을 정리하지 못하고 Kong route/consumer/key 를
orphan 으로 남겼다(3b-2).

deps: kong_helper(순수 Kong Admin wrapper) + db_deployment(msa_db, 동기). 둘 다 fb_utils
공용이고 이 모듈을 import 하지 않으므로 순환 없음.
"""
from utils import kong_helper
from utils.msa_db import db_deployment

# 게시 전용 외부 경로 prefix — 내부 서빙 `/deployment/`(익명 공유)와 분리.
# 비-`/api` 라 fb_ingress_management 리콘사일러가 스킵(generic key-auth 미부착).
EXTERNAL_API_PREFIX = "/ext"

# 게시(D6) route 남용가드 config — publish 시 /ext route 에 부착. 인라인 매직넘버 대신
# 여기 단일 정의(값 drift 방지, edge-device-plugins.yaml 규약 기반). 게시=외부 노출이라
# gross-abuse 상한만: rate=IP 당 분당 60(정상 사용엔 넉넉, policy=local=단일 Kong 레플리카 기준),
# size=10MB(LLM/VLM 페이로드 — 긴 프롬프트·base64 이미지·배치 — 를 막지 않는 총량 상한).
EXTERNAL_RATE_LIMIT_CONFIG = {"minute": 60, "limit_by": "ip", "policy": "local", "fault_tolerant": True}
EXTERNAL_REQUEST_SIZE_CONFIG = {"allowed_payload_size": 10}


def external_route_path(api_path: str) -> str:
    """게시 전용 Kong route path — publish(라우트 생성)와 공개 URL 이 같은 경로를 쓰도록 단일 정의."""
    return "{}/{}".format(EXTERNAL_API_PREFIX, api_path)


def api_consumer_name(deployment_id) -> str:
    """게시 consumer 이름(배포별 1:1). 리콘사일러가 살려두는 `dep-<digits>` 규약."""
    return "dep-{}".format(deployment_id)


def external_route_name(deployment_id) -> str:
    """게시 전용 route 의 Kong name(publish 생성 시 부여). 배포/api_path 소실 후에도 이 name 으로
    route 를 찾아 정리하기 위한 단일 정의(orphan sweep·teardown fallback·publish 공유)."""
    return "ext-dep-{}".format(deployment_id)


def teardown_deployment_api(deployment_id) -> None:
    """게시(D6) Kong 리소스 + deployment_api row 를 완전 취소(revoke). 멱등.

    publish 의 역연산: key-auth 크리덴셜 + dep-{id} consumer(=ACL group) + 전용 게시
    route(/ext/{api_path}) + deployment_api row 를 제거한다.

    row 가 없거나 DB blip 이어도 결정적 식별자(dep-{id}, /ext/{api_path})로 Kong 정리를
    시도한다 — DB 오류를 '이미 미게시'로 오인해 route/키를 살려두는 불완전 취소를 막기 위함.
    소유권 검증은 하지 않는다(호출부 책임): 외부 호출은 fb_deployment 가 wrapper 에서 검증,
    lifecycle(stop/delete) 은 내부 정리라 소유권 무관.

    부분 실패 안전성(3-way review HIGH): 크리덴셜(key-auth/consumer)을 **먼저** 지워
    '키 무효화'를 최우선한다 — route 가 남아도 유효 키가 없으면 401. 각 Kong 삭제는 독립
    시도(한 리소스 실패가 나머지를 건너뛰어 '유효 키 + 살아있는 route' 를 남기지 않도록).
    실패는 모아 마지막에 raise → 외부 unpublish 는 사용자에게 오류 노출(멱등 재시도 가능),
    lifecycle 은 best-effort 로 로깅. Kong 이 완전 불통인 극단(모든 삭제 실패)은 이 함수로
    완전 커버 불가 — 잔여 dep-* 를 주기 정리하는 리콘사일러가 완전한 해법(후속 과제).
    """
    row = db_deployment.get_deployment_api(deployment_id)
    consumer = (row or {}).get("api_consumer") or api_consumer_name(deployment_id)
    route_id = (row or {}).get("api_route_id")
    errors = []
    if not route_id:
        try:
            dep = db_deployment.get_deployment(deployment_id=deployment_id)
        except Exception:
            dep = None  # 2차 조회 실패해도 크리덴셜 삭제는 진행(키 무효화 우선)
        api_path = (dep or {}).get("api_path")
        # route 조회(Kong 조회)가 실패해도 크리덴셜 삭제(키 무효화)는 반드시 진행 — 유효 키를 살려둔 채
        # 함수가 이탈하면 '키 우선 무효화' 불변식이 깨진다. path·name 조회를 독립 try 로 분리해, path 조회
        # 일시 실패가 name 폴백까지 막지 않도록 한다. 실패는 errors 로 기록(unpublish 가 실패 노출·멱등
        # 재시도)하되 route_id 는 None 으로 남겨 route 삭제만 건너뛴다(남은 route 는 다음 orphan sweep 이 회수).
        if api_path:
            try:
                route_id = kong_helper.find_route_id_by_path(external_route_path(api_path))
            except Exception as e:
                errors.append("find_route_by_path: {!r}".format(e))
        if not route_id:
            try:
                # api_path 소실(배포 삭제)돼도 route name 으로 정리 — orphan sweep/lifecycle delete 견고성.
                route_id = kong_helper.find_route_id_by_name(external_route_name(deployment_id))
            except Exception as e:
                errors.append("find_route_by_name: {!r}".format(e))
    # 1) 크리덴셜 먼저(키 무효화 최우선). 각 단계 독립 — 실패해도 나머지 시도.
    try:
        kong_helper.delete_key_auths(consumer)   # 유효 키 제거(→ route 남아도 401)
    except Exception as e:
        errors.append("delete_key_auths: {!r}".format(e))
    try:
        kong_helper.delete_consumer(consumer)    # consumer + ACL group 멤버십 제거
    except Exception as e:
        errors.append("delete_consumer: {!r}".format(e))
    # 2) 전용 게시 route(부착 plugin: key-auth/acl/rate/size cascade 제거).
    if route_id:
        try:
            kong_helper.delete_route(route_id)
        except Exception as e:
            errors.append("delete_route: {!r}".format(e))
    # 3) DB row 삭제. delete_deployment_api 는 raise 대신 {result:False} 반환 → 명시 확인
    #    (실패 시 enabled 잔존 → GET/FE 가 계속 'published' 표시하는 것 방지).
    try:
        db_res = db_deployment.delete_deployment_api(deployment_id)
        if isinstance(db_res, dict) and not db_res.get("result"):
            errors.append("delete_deployment_api: {}".format(db_res.get("message")))
    except Exception as e:
        errors.append("delete_deployment_api: {!r}".format(e))

    if errors:
        raise Exception("teardown_deployment_api partial failure (deployment_id={}): {}".format(
            deployment_id, "; ".join(errors)))
