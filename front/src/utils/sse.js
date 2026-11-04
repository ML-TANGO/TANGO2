import { handleSessionExpired } from '@src/network';

/**
 * SSE(EventSource) 실패 분류 유틸.
 *
 * 왜 필요한가 —
 *  - 세션 만료 신호는 두 갈래다: 앱은 `200 + {status:0, expired:true}` 본문으로,
 *    게이트웨이(Kong)는 `HTTP 403`(HTML 본문) 으로 알린다. 이 플랫폼은 세션을
 *    Kong 에 위임했고, 만료되면 anonymous consumer 폴백 → request-termination(403)
 *    이라 401 이 아니다. 앱이 직접 내는 403(권한 부족)은 JSON 이므로 구분 가능.
 *  - `EventSource`(및 event-source-polyfill)는 실패 시 **본문을 읽을 수 없다**.
 *    그래서 SSE 만 쓰는 화면은 만료를 감지하지 못하고, 자동 로그아웃
 *    (network.js handleSessionExpired) 이 영원히 발동하지 않았다.
 *  - 반대로 "권한 없음/서버 에러" 는 앱이 스트림 대신 JSON 을 주는데, 이는
 *    재연결해도 영구 실패다(무한 재시도 + 토스트 폭주의 원인).
 *
 * event-source-polyfill 의 error 이벤트는 ConnectionEvent 로 `status` / `statusText`
 * / `headers` 를 함께 준다(node_modules/event-source-polyfill/src/eventsource.js).
 * 그 값으로 1차 분류하고, 판별이 안 되는 `200 + 비-스트림` 케이스만 같은 URL 을
 * 한 번 재조회해 본문(`expired`)을 확인한다.
 */

export const SSE_FAILURE = {
  /**
   * 세션 만료 **확정** — network.js 가 재확인까지 마쳤고 자동 로그아웃도 처리했다.
   * 호출측은 재연결하지 말 것(곧 /login 으로 이동하며 언마운트된다).
   * 게이트웨이가 거부했지만 확인 결과 세션이 멀쩡하면 EXPIRED 가 아니라 RETRY 가 온다.
   */
  EXPIRED: 'expired',
  /** 권한 없음/영구 실패 — 재연결해도 같은 결과. 호출측은 재연결 중단. */
  FATAL: 'fatal',
  /** 일시적 끊김(네트워크·프록시 타임아웃·파드 재시작) — 백오프 후 재연결. */
  RETRY: 'retry',
};

/**
 * 재연결 정책 — 6개 SSE 소비처가 **공유**한다.
 * 파일마다 상한/백오프를 따로 두면 정책이 조용히 갈린다(실제로 갈려 있었다:
 * 대시보드는 무한 재시도, PlaygroundHeader 는 6회 제한).
 */
export const SSE_RETRY = {
  BASE_DELAY_MS: 1000,
  MAX_DELAY_MS: 30000,
  /** 연속 실패 상한 — 초과 시 재연결 중단(영구히 죽은 서버에 계속 요청하지 않는다). */
  GIVE_UP_AFTER: 6,
};

/** 연속 실패 횟수(0-base) → 백오프 지연(ms). 상한 SSE_RETRY.MAX_DELAY_MS. */
export const sseRetryDelay = (attempt) =>
  Math.min(
    SSE_RETRY.BASE_DELAY_MS * 2 ** Math.max(0, attempt),
    SSE_RETRY.MAX_DELAY_MS,
  );

/**
 * SSE 재시도 상태. `useRef(createSseRetryState())` 로 컴포넌트 수명에 고정해 쓴다.
 *
 *  - `alive`: effect cleanup 에서 false 로 내린다. `classifySseFailure` 는 200+비스트림
 *    케이스에서 probe fetch 를 기다려 **최대 PROBE_TIMEOUT_MS 만큼 await 된다**. 그 사이
 *    사용자가 화면을 벗어나면 cleanup 이 이미 끝난 뒤 핸들러가 늦게 resolve 되어,
 *    아무도 추적하지 않는 타이머/EventSource 를 새로 만든다(정리 불가한 좀비 재연결 루프).
 *    → await 직후와 재연결 직전에 반드시 검사한다.
 *  - `attempt`/`notified`: effect 지역변수로 두면 재마운트마다 0 으로 초기화돼
 *    "첫 실패 1회만 안내" 가 무너지고 토스트 폭주가 되살아난다.
 */
export const createSseRetryState = () => ({
  alive: true,
  attempt: 0,
  notified: false,
});

const PROBE_TIMEOUT_MS = 5000;

/**
 * 같은 SSE URL 을 일반 GET 으로 1회 재조회해 실패 원인을 본문에서 확인한다.
 * 스트림이 정상 복구된 경우(text/event-stream)엔 즉시 끊고 RETRY 로 돌려준다
 * (본문을 끝까지 읽으면 스트림이라 끝나지 않는다).
 */
const probeFailure = async (url, headers) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      headers,
      credentials: 'include',
      signal: controller.signal,
    });
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');

    // 게이트웨이 종단(=만료)은 401, 또는 403 + 비-JSON(HTML) 본문이다.
    if (res.status === 401 || (res.status === 403 && !isJson)) {
      controller.abort();
      return SSE_FAILURE.EXPIRED;
    }

    if (!isJson) {
      // 스트림으로 돌아왔거나 판별 불가 → 일시 장애로 보고 재연결에 맡긴다.
      controller.abort();
      return SSE_FAILURE.RETRY;
    }
    const body = await res.json().catch(() => null);
    if (body?.expired) return SSE_FAILURE.EXPIRED;
    // status:0 + 스트림 아님 = 권한 없음/서버 에러 → 재시도 무의미.
    return SSE_FAILURE.FATAL;
  } catch (e) {
    // probe 자체 실패(네트워크/timeout) → 원인 미확정이므로 재연결 여지를 남긴다.
    return SSE_FAILURE.RETRY;
  } finally {
    clearTimeout(timer);
  }
};

/**
 * SSE onerror 핸들러에서 호출. 만료면 자동 로그아웃까지 수행하고 분류값을 돌려준다.
 *
 * @param {Object} params
 * @param {Event}  params.errorEvent EventSource onerror 이벤트(polyfill ConnectionEvent)
 * @param {string} params.url        연결에 사용한 SSE URL (probe 재사용)
 * @param {Object} [params.headers]  연결에 사용한 헤더 (probe 재사용)
 * @returns {Promise<'expired'|'fatal'|'retry'>}
 */
export const classifySseFailure = async ({ errorEvent, url, headers }) => {
  const status = errorEvent?.status;

  // ⚠️ 게이트웨이 거부는 **잠정** 신호다. handleSessionExpired 가 한 번 더 확인해
  // "정말 만료였는가" 를 돌려주므로 그 결과로만 EXPIRED 를 확정한다. 예전엔 확인 없이
  // EXPIRED 를 돌려줘, 오탐이면 세션은 멀쩡한데 소비처들이 재연결을 멈춰 스트림만 죽었다.
  if (status === 401) {
    return (await handleSessionExpired())
      ? SSE_FAILURE.EXPIRED
      : SSE_FAILURE.RETRY;
  }
  // 403 = 이 플랫폼의 만료 신호(게이트웨이 종단, HTML 본문).
  // 앱이 직접 내는 권한 부족 403 은 JSON 이므로 헤더가 읽히면 그걸로 구분하고,
  // 폴리필이 헤더를 안 주면 만료로 본다(SSE 라우트에 앱의 403 응답은 없다).
  if (status === 403) {
    const rawHeaders = errorEvent?.headers;
    const contentType =
      (typeof rawHeaders?.get === 'function'
        ? rawHeaders.get('content-type')
        : rawHeaders?.['content-type']) || '';
    if (contentType.includes('application/json')) return SSE_FAILURE.FATAL;
    return (await handleSessionExpired())
      ? SSE_FAILURE.EXPIRED
      : SSE_FAILURE.RETRY;
  }

  // status 200 인데 error = Content-Type 이 text/event-stream 이 아님
  //   → 앱이 스트림 대신 JSON(expired / forbidden / server error)을 반환한 경우.
  if (status === 200 && url) {
    const verdict = await probeFailure(url, headers);
    if (verdict === SSE_FAILURE.EXPIRED) {
      return (await handleSessionExpired())
        ? SSE_FAILURE.EXPIRED
        : SSE_FAILURE.RETRY;
    }
    return verdict;
  }

  // status 0/undefined = 연결 자체가 끊김(네트워크, 프록시 타임아웃, 파드 재시작).
  return SSE_FAILURE.RETRY;
};
