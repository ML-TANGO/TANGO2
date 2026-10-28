"""원격 생성 — 이미 떠 있는 배포(OpenAI 호환 shim)에 생성을 위임하는 클라이언트.

대상은 플랫폼의 OpenAI shim(`/api/playgrounds/{id}/openai/v1`)이다 — 서빙 pod 자체는
OpenAI HTTP API 를 노출하지 않으므로 shim 을 반드시 경유해야 한다(프롬프트 최적화
컨테이너가 이미 같은 경로를 소비해 잡 파드에서의 도달성이 확인돼 있다).

⚠️ 이 파일은 `evaluate_logickor_judge/judge.py` 의 원격 심판 클라이언트와 **같은 규약**
   (동시성·타임아웃·재시도·(text, error) 반환)을 의도적으로 그대로 따른다. 두 컨테이너는
   공유 파일이 없어(이미지가 다르고 judge.py 는 LogicKor 전용 templates 에 의존한다)
   코드가 갈라질 수밖에 없는 자리다 — 한쪽을 고치면 다른 쪽도 함께 봐야 한다.

⚠️ shim 은 body 의 model·temperature·max_tokens 를 **무시하고** 배포 시점 설정을 따른다.
   그리고 assistant 턴이 없으면 `_messages_to_prompt` 가 role 라벨 없이 content 만
   "\\n\\n" 으로 이어 붙인다 → MixATIS 의 system(UGEN 지침) + user 2턴은 role 분리 없이
   한 덩어리로 배포에 전달된다. 프롬프트 문자열 자체는 보존되지만 role 분리에 기대는
   지시 준수는 약해질 수 있다 → 로컬 경로(chat template 적용) 점수와 직접 비교하지 마라.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import urlparse

# 동시성 상한 — judge.py REMOTE_JUDGE_CONCURRENCY 와 같은 근거다. 순차 호출은 828 발화 ×
# 2문항 = 1656 건이라 벽시계가 폭발하고, 무제한 fan-out 은 배포 1개의 추론 큐를 넘겨
# 타임아웃을 만들며 shim 호출 1건이 플랫폼 BFF 요청을 최대 300초 점유한다.
REMOTE_CONCURRENCY = 8
# shim 내부 추론 타임아웃이 300초다(llm_playground `_SHIM_TIMEOUT`). 그보다 조금 길게
# 잡아야 우리 타임아웃이 shim 이 돌려주는 실제 에러 메시지를 덮어쓰지 않는다.
REMOTE_TIMEOUT = 330.0
# 순간 오류(연결 리셋·502·빈 응답)만 재시도한다. 형식 파싱 실패는 재시도 대상이 아니다 —
# 같은 프롬프트를 같은 배포에 다시 보내는 것이라 결과가 달라질 이유가 없다.
REMOTE_RETRIES = 2

# thinking 블록 마커. 원격 경로는 chat template 을 우리가 적용하지 않으므로
# `enable_thinking=False`(원본 generate_batch 가 걸던 것)를 걸 수 없다 → Qwen3 계열
# 배포는 사고 블록을 답변 앞에 붙일 수 있고, 그러면 UGEN 형식 파싱이 전부 빈 예측이 된다.
THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


def strip_think_block(text: str) -> str:
    """<think>…</think> 를 걷어낸다 — **원격 경로 전용**.

    닫는 태그가 있으면 그 뒤만 남기고, 열기만 있고 닫히지 않았으면(생성 상한에 잘린 경우)
    답변이 존재하지 않는 것이므로 빈 문자열을 돌려준다 — 사고과정을 답변인 척 파서에
    넘기면 형식 위반이 '내용 오류'로 뭉개진다.
    """
    t = text or ""
    if THINK_CLOSE in t:
        return t.split(THINK_CLOSE)[-1].strip()
    if THINK_OPEN in t:
        return ""
    return t


class RemoteEndpoint(NamedTuple):
    """검증이 끝난 원격 엔드포인트. 연결은 **검증한 IP** 로만 하고 Host 는 되돌린다.

      url         표시·기록용 원본 URL. 로그와 metrics.generate.endpoint 는 이걸 쓴다 —
                  IP 만 남기면 어느 배포였는지 사후에 추적할 수 없다.
      connect_url host 를 검증한 IP 로 치환한 URL. 실제 요청은 이것으로만 나간다.
      host_header 원본 host[:port]. IP 로 붙었으므로 Host 를 직접 세워야 shim 의
                  라우팅이 원래대로 동작한다.
      sni         https 일 때 TLS SNI·인증서 검증에 쓸 원본 hostname(http 면 None).
    """
    url: str
    connect_url: str
    host_header: str
    sni: Optional[str]

    def request_kwargs(self) -> dict:
        """모든 요청에 그대로 펼쳐 넣는다 — Host 복원 + (https) SNI/인증서 대상 복원."""
        kwargs: dict = {"headers": {"Host": self.host_header}}
        if self.sni:
            # httpx → httpcore 확장. IP 로 연결하면서도 TLS 핸드셰이크의 SNI 와 인증서
            # hostname 검증은 **원래 이름**으로 한다(검증을 끄지 않는다). 이 확장을 모르는
            # httpcore 라면 무시되고 인증서가 IP 와 불일치해 연결이 실패한다 —
            # fail-open 이 아니라 fail-closed 라 뚫리는 경로가 생기지 않는다.
            kwargs["extensions"] = {"sni_hostname": self.sni}
        return kwargs


def validate_base_url(raw: Optional[str], key: str = "generate_base_url"
                      ) -> Optional[RemoteEndpoint]:
    """params 로 받은 원격 엔드포인트 검증. 빈 값이면 None(= 종전 로컬 경로).

    검증 없이 열면 SSRF 다. llm_evaluation `_validate_local_url`(evaluation/service.py)
    및 evaluate_logickor_judge `_resolve_remote_base_url` 과 같은 목적·수준으로 막는다:
      - scheme 은 http/https 만
      - 경로에 '..' 금지, userinfo(자격증명) 금지
      - **모든** resolve 결과를 검사한다(라운드로빈/멀티레코드로 한 건만 통과시키는 우회
        차단). link-local(169.254.169.254 등 메타데이터)·multicast·unspecified 면 거부.
      - 검증한 IP 를 **연결에 고정**한다(connect_url). 호스트명을 그대로 넘기면 httpx 가
        연결 시점에 다시 resolve 해 DNS rebinding TOCTOU 창이 열린다 — 검사한 주소와
        실제로 붙는 주소가 달라질 수 있다.
    loopback/private 는 허용한다 — 대상이 클러스터 내부 svc 라 막으면 기능이 성립하지 않는다
    (is_reserved 는 IPv6 loopback(::1)까지 잡아 127.0.0.1 과 비일관이라 쓰지 않는다).

    IP 고정은 잡 시작 시 1회다. 대상은 Service DNS 이름 → ClusterIP 이고 ClusterIP 는
    Service 수명 동안 고정이라(파드가 재스케줄돼도 바뀌지 않는다) 잡이 도는 내내 유효하다.
    """
    raw = str(raw or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{key} must be http or https")
    if not parsed.hostname:
        raise ValueError(f"{key} has no host")
    if parsed.username or parsed.password:
        raise ValueError(f"{key} must not carry credentials")
    if ".." in (parsed.path or ""):
        raise ValueError(f"{key} path must not contain '..'")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port)
    except OSError as exc:
        # 1656 건을 쏘아 전량 실패하는 대신 바로 멈춘다(사유가 명확하다).
        raise ValueError(f"{key} host not resolvable: {parsed.hostname}") from exc
    safe_ip = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ValueError(f"{key} resolves to a disallowed address")
        if safe_ip is None:
            safe_ip = info[4][0]
    if safe_ip is None:
        raise ValueError(f"{key} host not resolvable: {parsed.hostname}")
    return RemoteEndpoint(url=raw.rstrip("/"),
                          connect_url=_pin_url(parsed, safe_ip),
                          host_header=_host_header(parsed),
                          sni=parsed.hostname if parsed.scheme == "https" else None)


def _bracket(host: str) -> str:
    """IPv6 리터럴은 대괄호로 감싼다(그러지 않으면 URL 의 포트 구분자와 섞인다)."""
    return f"[{host}]" if ":" in host else host


def _pin_url(parsed, safe_ip: str) -> str:
    """검증한 IP 를 host 자리에 박은 base URL. query/fragment 는 base 에 의미가 없어 버린다
    (종전에도 'base?x=1' + '/models' 는 깨진 URL 이 됐다)."""
    port_seg = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{_bracket(safe_ip)}{port_seg}{(parsed.path or '').rstrip('/')}"


def _host_header(parsed) -> str:
    """되돌릴 Host 헤더값 — 원본 host[:port]."""
    host = _bracket(parsed.hostname)
    return f"{host}:{parsed.port}" if parsed.port else host


def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def detect_model(endpoint: RemoteEndpoint) -> str:
    """GET {base}/models 의 data[0].id — 배포가 서빙하는 모델 식별자.

    실패하면 예외 — 엔드포인트가 죽었는데 1656 건을 쏘아 전량 실패로 끝나는 것보다
    여기서 멈추는 게 낫다.
    연결은 검증한 IP(connect_url)로 하고 Host 는 되돌린다(validate_base_url 참조).
    """
    import httpx

    url = _url(endpoint.connect_url, "/models")
    shown = _url(endpoint.url, "/models")   # 오류 문구는 사용자가 준 주소로 말한다
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, **endpoint.request_kwargs())
    except Exception as exc:   # noqa: BLE001 — 연결/DNS/TLS 무엇이든 같은 진단이 필요하다
        # 원문 예외(ConnectError: All connection attempts failed)만으로는 어느 주소를
        # 못 잡았는지 알 수 없다. 잡 실패 메시지가 그대로 화면에 뜨므로 URL 을 붙인다.
        # 고정한 IP 도 같이 붙인다 — 이름은 풀렸는데 그 IP 가 안 열리는 경우가 갈린다.
        raise RuntimeError(f"생성 endpoint {shown}(→ {url}) 에 연결할 수 없다 "
                           f"({type(exc).__name__}: {exc}) — 배포가 실행 중인지, "
                           f"잡 파드에서 도달 가능한 주소인지 확인하라") from exc
    if r.status_code != 200:
        raise RuntimeError(f"생성 endpoint {shown} → HTTP {r.status_code}: {r.text[:200]}")
    try:
        data = (r.json() or {}).get("data") or []
    except ValueError as exc:
        raise RuntimeError(f"생성 endpoint {shown} 응답이 JSON 이 아니다: "
                           f"{str(r.text)[:200]}") from exc
    if not data or not isinstance(data[0], dict) or not data[0].get("id"):
        raise RuntimeError(f"생성 endpoint {shown} 응답에 모델이 없다: {str(r.text)[:200]}")
    return str(data[0]["id"])


def _one_factory(client, url: str, model: str, max_output_tokens: int,
                 req_kwargs: dict):
    """단건 호출 클로저 — (text, None) 또는 (None, error). 예외를 올리지 않는다.

    req_kwargs 는 RemoteEndpoint.request_kwargs() 결과다(Host 복원 + https SNI). 읽기
    전용이라 워커 스레드가 공유해도 안전하다.
    """
    def one(messages):
        # temperature/max_tokens 는 플랫폼 shim 이 무시하지만 그대로 싣는다 — 이 컨테이너를
        # 일반 OpenAI 호환 엔드포인트(vLLM serve 등)에 붙였을 때는 실제로 먹기 때문이다.
        payload = {"model": model, "messages": messages,
                   "temperature": 0.0, "max_tokens": max_output_tokens,
                   "stream": False}
        last = "unknown error"
        for attempt in range(REMOTE_RETRIES + 1):
            try:
                r = client.post(url, json=payload, **req_kwargs)
                if r.status_code != 200:
                    last = f"HTTP {r.status_code}: {r.text[:200]}"
                else:
                    choices = (r.json() or {}).get("choices") or []
                    msg = (choices[0] or {}).get("message") if choices else None
                    text = (msg or {}).get("content")
                    if isinstance(text, str) and text.strip():
                        return text, None
                    last = "empty content in response"
            except Exception as exc:   # noqa: BLE001 — 네트워크/파싱 무엇이든 재시도 대상
                last = f"{type(exc).__name__}: {exc}"
            if attempt < REMOTE_RETRIES:
                time.sleep(2.0 * (attempt + 1))
        return None, last
    return one


def batch_chat(endpoint: RemoteEndpoint, model: str, max_output_tokens: int
               ) -> Callable[[List[List[Dict[str, str]]]],
                             List[Tuple[Optional[str], Optional[str]]]]:
    """제한된 워커 풀로 /chat/completions 를 호출한다 → (text, error) 리스트.

    **입력 순서를 보존한다**(호출부가 발화와 zip 으로 짝지으므로 순서가 어긋나면 예측이
    다른 발화에 붙는다 — pool.map 이 순서를 보장한다).
    개별 실패는 예외로 올리지 않고 error 문자열로 내려보낸다 — 1건 실패로 배치를 버리지
    않되, 실패 자체는 호출부가 세어 통계와 전량 실패 판정에 쓴다.
    """
    import httpx
    from concurrent.futures import ThreadPoolExecutor

    url = _url(endpoint.connect_url, "/chat/completions")
    req_kwargs = endpoint.request_kwargs()

    def run(conversations):
        limits = httpx.Limits(max_connections=REMOTE_CONCURRENCY,
                              max_keepalive_connections=REMOTE_CONCURRENCY)
        # httpx.Client 는 스레드 세이프하고 커넥션 풀을 공유한다 — 워커마다 새로 만들면
        # 배치마다 TCP 핸드셰이크를 그만큼 반복한다. 풀은 IP origin 에 키되므로 재resolve
        # 없이 고정한 주소로만 붙는다.
        with httpx.Client(timeout=REMOTE_TIMEOUT, limits=limits) as client:
            one = _one_factory(client, url, model, max_output_tokens, req_kwargs)
            with ThreadPoolExecutor(max_workers=REMOTE_CONCURRENCY) as pool:
                return list(pool.map(one, conversations))
    return run
