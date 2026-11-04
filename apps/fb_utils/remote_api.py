"""외부 LLM 배포(deploy_type='remote_api') 어댑터 — 상용 API 3사 + 사용자 엔드포인트.

pod 을 띄우지 않는다. 이 배포는 GPU·helm·NFS 를 쓰지 않고, llm_playground 프로세스가
직접 외부로 나간다(egress 는 실측 확인됨). 어댑터의 계약은 단 하나 —
`_infer_question`(service.py) 과 **같은 반환 형태**를 만들어, 추론 화면·일괄 추론·
이중모델·OpenAI shim 이 무수정으로 동작하게 하는 것이다.

이 파일의 방어 두 축은 llm_evaluation 에서 옮겨 왔다(그쪽 주석이 "예정된 외부 API 배포
작업이 같은 입력을 다시 받으므로 그때 이 함수를 배포 표면으로 옮긴다"고 이 이관을
명시적으로 예고해 두었다):
  1. 상용 provider — 호스트를 **우리가 고정**한다(constants.JUDGE_PROVIDER_HOSTS).
     사용자 입력은 키뿐이라 키가 엉뚱한 호스트로 새거나 리다이렉트에 끌려가는 SSRF
     경로가 애초에 생기지 않는다.
  2. endpoint provider — 사용자가 URL 을 주는 유일한 경우. validate_endpoint_url 이
     DNS rebinding TOCTOU(resolve 한 IP 로 직접 connect)·멀티레코드 우회·link-local
     metadata 를 막는다.

⚠️ 키는 **헤더로만** 전달한다(URL 쿼리 금지 — 예외 메시지·액세스 로그에 남는다).
⚠️ 예외 메시지에 키를 절대 싣지 않는다(_safe_err 로 응답 본문도 잘라서 넣는다).
"""
import ipaddress
import json
import socket
from urllib.parse import urlparse, quote

import httpx

# ── provider 정본 ────────────────────────────────────────────────────────────
# 상용 3사 + endpoint(사용자 URL). llm_evaluation 의 JUDGE_PROVIDERS 와 같은 집합이며,
# 'local' 을 'endpoint' 로만 고쳐 불렀다(배포 표면에서는 "로컬"이 아니라 "외부 엔드포인트").
PROVIDER_CHATGPT = "chatgpt"
PROVIDER_CLAUDE = "claude"
PROVIDER_GEMINI = "gemini"
PROVIDER_ENDPOINT = "endpoint"

PROVIDERS = (PROVIDER_CHATGPT, PROVIDER_CLAUDE, PROVIDER_GEMINI, PROVIDER_ENDPOINT)
COMMERCIAL_PROVIDERS = (PROVIDER_CHATGPT, PROVIDER_CLAUDE, PROVIDER_GEMINI)

# 상용 provider egress 화이트리스트 — 호스트 고정. 사용자 입력은 키뿐.
PROVIDER_HOSTS = {
    PROVIDER_CHATGPT: "api.openai.com",
    PROVIDER_CLAUDE: "api.anthropic.com",
    PROVIDER_GEMINI: "generativelanguage.googleapis.com",
}
# FE 가 초기 선택으로 쓰는 기본 모델(front_etri 목업 COMMERCIAL_JUDGES 와 같은 값).
PROVIDER_DEFAULT_MODEL = {
    PROVIDER_CHATGPT: "gpt-4o",
    PROVIDER_CLAUDE: "claude-opus-4-8",
    PROVIDER_GEMINI: "gemini-2.0-flash",
}
PROVIDER_LABEL = {
    PROVIDER_CHATGPT: "ChatGPT",
    PROVIDER_CLAUDE: "Claude",
    PROVIDER_GEMINI: "Gemini",
    PROVIDER_ENDPOINT: "외부 엔드포인트",
}

# Anthropic 은 버전 헤더가 필수다(없으면 400).
ANTHROPIC_VERSION = "2023-06-01"

# 응답 상한. 상용 API 는 기본값이 짧아(특히 Anthropic 은 max_tokens 필수) 명시한다.
DEFAULT_MAX_TOKENS = 2048
# Kong 게이트웨이가 60s 에서 끊는다 → 그보다 먼저 우리가 끊어 원인이 드러나게 한다.
DEFAULT_TIMEOUT = 55.0
# 도달성 확인(verify) 예산. 상용 API 는 max_tokens=8 ping 이 1~3초지만, 자체 서빙
# 엔드포인트는 max_tokens 를 무시하기도 하고(우리 OpenAI shim 이 그렇다 — body 의
# 생성 파라미터를 의도적으로 버린다) 큐가 밀리면 수십 초가 걸린다. 20s/30s 로 잡았더니
# 정상 엔드포인트가 실패로 찍혔다(실측). 저장 PUT·시작 POST 는 브라우저→Kong(60s)
# 경로라 그 아래여야 하므로 45s 가 상한선이다.
VERIFY_TIMEOUT = 45.0

# 필드 길이 상한 — 입력 경계 검증(DB JSON 폭주 방지).
MAX_MODEL_LEN = 128
MAX_URL_LEN = 512


class RemoteApiError(Exception):
    """외부 호출 실패. 메시지에 키를 담지 않는다."""


def _safe_err(resp) -> str:
    """응답 본문을 예외에 실을 수 있는 형태로 자른다(JSON 이 아닐 수 있음 — 프록시 HTML 등)."""
    try:
        body = json.dumps(resp.json())[:300]
    except Exception:
        body = (resp.text or "")[:300]
    return f"HTTP {resp.status_code}: {body}"


def normalize_provider(provider):
    p = (provider or "").strip().lower()
    if p not in PROVIDERS:
        raise RemoteApiError(
            f"지원하지 않는 provider 입니다: {p!r} (가능: {', '.join(PROVIDERS)})")
    return p


def validate_endpoint_url(base_url):
    """사용자 엔드포인트 SSRF 가드. 반환: (연결용 검증 IP, Host 헤더값).

    llm_evaluation `_validate_local_url` 이식. DNS rebinding TOCTOU 차단: 여기서 resolve
    한 IP 를 호출부가 그대로 connect 에 쓴다(httpx 재resolve 회피). 모든 resolve 결과를
    검사(라운드로빈/멀티레코드 우회 방지). metadata(link-local 169.254/fe80)·multicast·
    unspecified 차단. loopback/private 는 사내 서빙 특성상 허용(차단하면 기능 불가) —
    is_reserved 는 IPv6 loopback(::1)까지 잡아 127.0.0.1 과 비일관이라 쓰지 않는다.
    (운영 egress 정책으로 추가 제한 권장.)"""
    if not base_url:
        raise RemoteApiError("endpoint provider 는 base_url 이 필요합니다")
    if len(base_url) > MAX_URL_LEN:
        raise RemoteApiError("base_url 이 너무 깁니다")
    p = urlparse(base_url)
    if p.scheme not in ("http", "https"):
        raise RemoteApiError("base_url 은 http 또는 https 여야 합니다")
    host = p.hostname
    if not host:
        raise RemoteApiError("base_url 호스트가 올바르지 않습니다")
    if ".." in (p.path or ""):
        raise RemoteApiError("base_url 경로에 '..' 을 쓸 수 없습니다")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except Exception:
        raise RemoteApiError("base_url 호스트를 resolve 할 수 없습니다")
    safe_ip = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise RemoteApiError("base_url 이 허용되지 않는 주소로 resolve 됩니다")
        if safe_ip is None:
            safe_ip = info[4][0]
    if safe_ip is None:
        raise RemoteApiError("base_url 호스트를 resolve 할 수 없습니다")
    host_header = f"{host}:{p.port}" if p.port else host
    return safe_ip, host_header


def validate_config(provider, model=None, base_url=None):
    """배포 구성 검증 → 영속할 config dict(키 제외). 키는 K8s Secret 에만 둔다."""
    provider = normalize_provider(provider)
    # endpoint 는 URL 을 먼저 본다 — 이 provider 에는 기본 모델이 없어서, 모델 검사를
    # 먼저 하면 URL 을 빠뜨렸을 때 "모델명을 입력하세요"라는 엉뚱한 안내가 나간다.
    if provider == PROVIDER_ENDPOINT:
        validate_endpoint_url(base_url)          # 형식·주소 검증(연결은 추론 시점에)
    model = (model or "").strip() or PROVIDER_DEFAULT_MODEL.get(provider)
    if not model:
        raise RemoteApiError("모델명을 입력하세요 (외부 엔드포인트가 서빙하는 모델명)")
    if len(model) > MAX_MODEL_LEN:
        raise RemoteApiError("모델명이 너무 깁니다")
    cfg = {"provider": provider, "model": model}
    if provider == PROVIDER_ENDPOINT:
        cfg["base_url"] = base_url.strip()
    return cfg


def _build_request(cfg, api_key, prompt, max_tokens=DEFAULT_MAX_TOKENS):
    """provider → (url, headers, body, host_header, connect_ip).

    `_messages_to_prompt`(shim 의 정방향, 단일 프롬프트로 접기)의 역방향 — 단일 질문을
    provider 별 messages 스키마로 편다. 상용 호스트는 PROVIDER_HOSTS 로 고정하므로
    connect_ip 는 None(httpx 의 일반 resolve 사용). endpoint 만 검증된 IP 로 직결한다.
    """
    provider = cfg["provider"]
    model = cfg["model"]

    if provider == PROVIDER_CHATGPT:
        return (
            f"https://{PROVIDER_HOSTS[provider]}/v1/chat/completions",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {"model": model, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": max_tokens},
            None, None,
        )

    if provider == PROVIDER_CLAUDE:
        return (
            f"https://{PROVIDER_HOSTS[provider]}/v1/messages",
            {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION,
             "Content-Type": "application/json"},
            {"model": model, "max_tokens": max_tokens,
             "messages": [{"role": "user", "content": prompt}]},
            None, None,
        )

    if provider == PROVIDER_GEMINI:
        # 모델명이 URL 경로에 들어간다 → 보간 전 인코딩(경로 주입 차단).
        # 키는 헤더(x-goog-api-key)로 보낸다 — 쿼리(?key=)는 로그에 남는다.
        return (
            f"https://{PROVIDER_HOSTS[provider]}/v1beta/models/"
            f"{quote(model, safe='')}:generateContent",
            {"x-goog-api-key": api_key, "Content-Type": "application/json"},
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"maxOutputTokens": max_tokens}},
            None, None,
        )

    # endpoint — OpenAI 호환으로 간주(vLLM/TGI/Ollama 등 사실상 표준).
    safe_ip, host_header = validate_endpoint_url(cfg.get("base_url"))
    base = cfg["base_url"].rstrip("/")
    p = urlparse(base)
    # 검증된 IP 로 직결하고 Host 헤더로 가상호스트를 살린다(재resolve 회피 = TOCTOU 차단).
    origin = f"{p.scheme}://{safe_ip}:{p.port}" if p.port else f"{p.scheme}://{safe_ip}"
    path = (p.path or "").rstrip("/")
    # OpenAI 호환 base_url 은 관례상 `/v1` 을 포함한다(vLLM/TGI 문서 기본형). 사용자가
    # 어느 형태로 넣든 받도록, 이미 /v1 로 끝나면 그 위에 얹고 아니면 /v1 을 붙인다
    # (그러지 않으면 /v1/v1/chat/completions 가 되어 404 가 난다).
    suffix = "/chat/completions" if path.endswith("/v1") else "/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Host": host_header}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return (
        f"{origin}{path}{suffix}",
        headers,
        {"model": model, "messages": [{"role": "user", "content": prompt}],
         "max_tokens": max_tokens},
        host_header, safe_ip,
    )


def _extract_text(provider, data):
    """provider 응답 → 출력 텍스트. 형태가 어긋나면 빈 문자열(추론 자체를 죽이지 않는다)."""
    try:
        if provider in (PROVIDER_CHATGPT, PROVIDER_ENDPOINT):
            return (data["choices"][0]["message"]["content"] or "").strip()
        if provider == PROVIDER_CLAUDE:
            # content 는 블록 배열 — text 블록만 이어 붙인다.
            return "".join(
                b.get("text", "") for b in (data.get("content") or [])
                if isinstance(b, dict) and b.get("type") == "text"
            ).strip()
        if provider == PROVIDER_GEMINI:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    except (KeyError, IndexError, TypeError):
        return ""
    return ""


async def infer(cfg, api_key, prompt, timeout=DEFAULT_TIMEOUT,
                max_tokens=DEFAULT_MAX_TOKENS):
    """외부 LLM 1건 추론 → 출력 텍스트.

    `_infer_question`(service.py) 과 같은 자리에 쓰이도록 **문자열 하나**를 돌려준다."""
    if not prompt or not str(prompt).strip():
        raise RemoteApiError("질문이 비어 있습니다")
    provider = cfg["provider"]
    if provider in COMMERCIAL_PROVIDERS and not api_key:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} API 키가 없습니다 — 배포 설정을 확인하세요")

    url, headers, body, _host, _ip = _build_request(cfg, api_key, str(prompt), max_tokens)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 응답이 {timeout:.0f}초 안에 오지 않았습니다")
    except Exception as e:
        # 키가 섞일 여지가 없는 전송 계층 오류만 타입명으로 보고한다.
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 연결 실패: {type(e).__name__}")

    if resp.status_code == 401 or resp.status_code == 403:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 인증 실패 — API 키를 확인하세요")
    if resp.status_code == 429:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 사용량 한도(429)에 걸렸습니다")
    if resp.status_code != 200:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 호출 실패 {_safe_err(resp)}")

    try:
        data = resp.json()
    except Exception:
        raise RemoteApiError(f"{PROVIDER_LABEL[provider]} 응답이 JSON 이 아닙니다")
    return _extract_text(provider, data)


async def verify(cfg, api_key):
    """배포 시작 시 도달성 확인 — 최소 프롬프트 1건. 실패하면 예외(=배포 시작 실패)."""
    await infer(cfg, api_key, "ping", timeout=VERIFY_TIMEOUT, max_tokens=8)
    return True


def provider_catalog():
    """FE 가 렌더할 provider 목록 — 하드코딩 금지(목록의 정본은 여기)."""
    return [
        {"id": p, "label": PROVIDER_LABEL[p],
         "default_model": PROVIDER_DEFAULT_MODEL.get(p),
         "requires_url": p == PROVIDER_ENDPOINT,
         "requires_key": p in COMMERCIAL_PROVIDERS}
        for p in PROVIDERS
    ]
