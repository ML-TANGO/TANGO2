import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';

// --- 설정 변수 (Configuration) ---
const KEYCLOAK_URL = 'https://keycloak.suredatalab.kr/realms/beymons/protocol/openid-connect/token'; // Keycloak 토큰 엔드포인트
const KEYCLOAK_CLIENT_ID = 'test'; // Keycloak 클라이언트 ID
const TARGET_API_URL = 'https://devel.beymons.kr/api/collects'; // 데이터를 전송할 API 엔드포인트
const VU = 100; // 테스트 유저 개수
const NODE_IDS_COUNT = 15; // 테스트에 사용할 노드 ID의 개수
const GATEWAY_LIST = [
    "TG000000000001",
    "TG000000000002",
    "TG000000000003",
    "TG000000000004",
    "TG000000000005",
    "TG000000000006",
    "TG000000000007",
    "TG000000000008",
    "TG000000000009"
];

// 테스트할 노드 ID 목록을 미리 생성
const nodeIds = new SharedArray('node_ids', function () {
    const ids = [];
    for (let i = 1; i <= NODE_IDS_COUNT; i++) {
        // TN000000000001, TN000000000002, ... 형식으로 생성
        ids.push(`TN${String(i).padStart(12, '0')}`);
    }
    return ids;
});

// --- 데이터 생성 함수 (Data Creation Function) ---
/**
 * 주어진 형식에 맞춰 임의의 데이터를 생성합니다.
 * @param {string} nodeId - 데이터가 속할 노드 ID
 * @returns {object} - 생성된 데이터 객체
 */
function dataCreation(nodeId) {
    const minTemp = 15.0;
    const maxTemp = 30.0;
    const minRssi = -90;
    const maxRssi = -40;

    // 30.0 ~ 60.0 사이의 임의의 소수점 첫째 자리까지의 온도 생성
    const generateTemp = () => Math.round((Math.random() * (maxTemp - minTemp) + minTemp) * 10) / 10;

    // -90 ~ -40 사이의 임의의 정수 RSSI 값 생성
    const generateRssi = () => Math.floor(Math.random() * (maxRssi - minRssi + 1)) + minRssi;

    return {
        "data": [
            {
                "node_id": nodeId,
                "1": [
                    {
                        "invalid": true,
                        "1": {
                            "temp": generateTemp()
                        },
                        "2": {
                            "temp": generateTemp()
                        }
                    }
                ],
                "rssi": [
                    {
                        "device": "01",
                        "rssi": generateRssi()
                    }
                ]
            }
        ]
    };
}

// --- 옵션 (Options) ---
export const options = {
    // 테스트 목표 설정
    stages: [
        { duration: '0s', target: VU }, // 최대 VU까지 ramp-up
        { duration: '300s', target: VU }, // 30초 동안 최대로 유지
        { duration: '0s', target: 0 },  // 0 VU로 ramp-down
    ],
    thresholds: {
        http_req_failed: ['rate<0.01'], // 요청 실패율 1% 미만
        http_req_duration: ['p(95)<200'], // 95% 응답 시간이 200ms 미만
    },
};

// --- 설정 함수: Keycloak 인증 (Setup Function) ---
// 테스트 시작 전 Keycloak 토큰을 획득하여 테스트 전체에서 사용
export function setup() {
    console.log('--- Keycloak 인증 시작 ---');
    const payload = {
        grant_type: 'client_credentials', 
        client_id: KEYCLOAK_CLIENT_ID,
        client_secret: __ENV.KEYCLOAK_CLIENT_SECRET,
        // scope: 'openid', // 필요한 경우 추가
    };

    const params = {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    };

    const res = http.post(KEYCLOAK_URL, payload, params);

    check(res, {
        'Keycloak 인증 성공': (r) => r.status === 200,
        'Access Token 획득': (r) => r.json() && r.json().access_token !== undefined,
    });

    if (res.status !== 200) {
        console.error('Keycloak 인증 실패:', res.body);
        throw new Error('Keycloak 인증에 실패했습니다. 설정을 확인하세요.');
    }

    const accessToken = res.json('access_token');
    console.log('Keycloak 인증 성공. Access Token 획득.');

    // 테스트 함수(default)로 전달할 객체 반환
    return {
        accessToken: accessToken,
    };
}

// --- 메인 부하 테스트 함수 (Main Test Function) ---
export default function (data) {
    // setup() 함수에서 전달받은 토큰
    const accessToken = data.accessToken;

    // 현재 가상 사용자(VU)에 기반하여 노드 ID 선택
    const nodeIdIndex = __VU % nodeIds.length;
    const currentNodeId = nodeIds[nodeIdIndex];

    // 1. 전송할 데이터 생성
    const payloadObject = dataCreation(currentNodeId);
    const payload = {
        "siteId": "sdl",
        "gatewayId": GATEWAY_LIST[__ITER % GATEWAY_LIST.length],
        "size": JSON.stringify(payloadObject).length,
        "data": payloadObject,
    };

    // 2. HTTP 요청 헤더 설정 (인증 토큰 및 JSON 형식 지정)
    const params = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`, // 획득한 Access Token 사용
        },
    };

    // 3. API 엔드포인트로 데이터 전송
    const res = http.post(TARGET_API_URL, JSON.stringify(payload), params);

    // 4. 응답 확인
    check(res, {
        'API 호출 성공 (200/201)': (r) => r.status === 200 || r.status === 201,
        '응답 시간 500ms 미만': (r) => r.timings.duration < 500,
    });

    // VU 당 요청 간격 조절
    sleep(0.1);
}
