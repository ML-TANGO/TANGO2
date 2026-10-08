// SDS(선박 항해) 샘플의 AIS 표(input_data.csv) 컬럼 규약 한 곳. 표 헤더 한글화·단위와
// 이미지 위 바운딩박스 추출이 같은 헤더 이름에 걸려 있어, 나뉘면 한쪽만 고쳐져 어긋난다.
// 헤더가 AIS 가 아니면(일반 CSV 데이터셋) 전부 무해하게 통과 — 원래 헤더·전체 열 그대로.

// 표에서 감출 열 — 좌표 숫자는 채점자가 읽을 값이 아니고, 같은 정보를 이미지 위 박스로 본다.
const BBOX_COLUMNS = ['bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'];

// 컬럼 → i18n 키 꼬리. 단위는 헤더에만 넣는다(셀마다 붙이면 숫자 비교가 어려워진다).
const COLUMN_KEYS = {
  timestamp: 'timestamp',
  my_ship: 'myShip',
  ship_id: 'shipId',
  length: 'length',
  width: 'width',
  draft: 'draft',
  latitude: 'latitude',
  longitude: 'longitude',
  knot: 'knot',
  heading: 'heading',
  cpa: 'cpa',
  tcpa: 'tcpa',
};

// 헤더 셀 정규화 — BOM(BE 가 utf-8 로 읽어 첫 셀에 남을 수 있다)·공백·대소문자.
const normalize = (cell) =>
  String(cell ?? '')
    .replace(/^\uFEFF/, '')
    .trim()
    .toLowerCase();

const toNumber = (value) => {
  const text = String(value ?? '').trim();
  if (!text) return NaN;
  const n = Number(text);
  return Number.isFinite(n) ? n : NaN;
};

export const isBboxColumn = (cell) => BBOX_COLUMNS.includes(normalize(cell));

export const aisColumnLabel = (t, cell) => {
  const key = COLUMN_KEYS[normalize(cell)];
  return key ? t(`evaluation.expert.ais.${key}`) : String(cell ?? '');
};

// 표 셀 표시값. 0/1 코드처럼 그대로 두면 오독되는 값만 바꾼다(원본 CSV 불변).
// tcpa 는 원본 단위(초) 그대로 둔다 — 헤더가 ETRI 표기 'TCPA(sec)' 라 변환하면 오히려 어긋난다.
// (생성 프롬프트에도 같은 값이 "TCPA:307.87초" 로 실린다.)
export const aisCellText = (t, cell, value) => {
  const col = normalize(cell);
  if (col === 'my_ship') {
    const code = toNumber(value);
    if (code === 1) return t('evaluation.expert.ais.own');
    if (code === 0) return t('evaluation.expert.ais.other');
    return value;
  }
  return value;
};

// ── CPA/TCPA 계산 — ETRI 제공 식(preprocess.py 의 local_xy·vel_xy 와 동일) ─────────────
// 항해사는 충돌 위험을 CPA(최근접 거리, 0 에 가까우면 충돌)·TCPA(최근접점 도달 시간)로 판단한다.
// sds_eval CSV 는 시뮬레이터가 cpa·tcpa 열을 싣지만 열이 없는 SDS 데이터셋이 있어, 그때만
// 위경도·속력·침로로 계산해 같은 열 이름·단위(NM, 초)로 붙인다. 시뮬레이터 값과 대조 결과
// 타선 491척 중앙값 차이 CPA 0.0016NM·TCPA 0.38초 — 같은 지표다. (원본 CSV 불변, 표시 전용.)
const METERS_PER_NAUTICAL_MILE = 1852;
const EARTH_RADIUS_M = 6371000;
const MPS_PER_KNOT = 0.514444;

const toRadians = (degrees) => (degrees * Math.PI) / 180;

// 속력(kt)·침로(°, 북 기준 시계방향) → [동, 북] 속도(m/s).
const velocityEastNorth = (knot, heading) => {
  const speed = knot * MPS_PER_KNOT;
  return [
    speed * Math.sin(toRadians(heading)),
    speed * Math.cos(toRadians(heading)),
  ];
};

// TCPA(초). 양수면 앞으로 최근접점에 도달, 음수면 이미 지나 멀어지는 중. 상대속도 0 이면 0.
export const computeTcpaSeconds = (posEast, posNorth, velEast, velNorth) => {
  const speedSquared = velEast ** 2 + velNorth ** 2;
  if (speedSquared <= 1e-9) return 0;
  return -(posEast * velEast + posNorth * velNorth) / speedSquared;
};

// CPA(NM). TCPA 가 음수면(멀어지는 중) 현재 거리.
export const computeCpaNauticalMiles = (
  posEast,
  posNorth,
  velEast,
  velNorth,
) => {
  const t = Math.max(
    computeTcpaSeconds(posEast, posNorth, velEast, velNorth),
    0,
  );
  return (
    Math.hypot(posEast + velEast * t, posNorth + velNorth * t) /
    METERS_PER_NAUTICAL_MILE
  );
};

// csv_rows 에 cpa·tcpa 열이 없으면 자선 기준으로 계산해 붙인 새 배열을 돌려준다.
// 열이 이미 있거나(CSV 값 우선) AIS 가 아니거나 자선이 정확히 1척이 아니면 원본 그대로 —
// 기준선이 모호하면 틀린 CPA 를 내느니 안 보이는 쪽이 안전하다.
// 자선 행은 시뮬레이터 CSV 와 같이 0 — 형식도 CSV 와 맞춘다(cpa 소수 4자리·tcpa 2자리).
// 값이 비어 계산할 수 없는 타선은 '-' — 빈칸은 '위험 없음'으로 읽힐 수 있다.
export const withCpaTcpa = (rows) => {
  if (!Array.isArray(rows) || rows.length < 2 || !Array.isArray(rows[0])) {
    return rows;
  }
  const head = rows[0].map(normalize);
  if (head.includes('cpa') || head.includes('tcpa')) return rows;
  const [iOwn, iLat, iLon, iKnot, iHeading] = [
    'my_ship',
    'latitude',
    'longitude',
    'knot',
    'heading',
  ].map((name) => head.indexOf(name));
  if ([iOwn, iLat, iLon, iKnot, iHeading].some((i) => i < 0)) return rows;

  const body = rows.slice(1);
  const owns = body.filter(
    (row) => Array.isArray(row) && toNumber(row[iOwn]) === 1,
  );
  if (owns.length !== 1) return rows;
  const [own] = owns;
  const [ownLat, ownLon, ownKnot, ownHeading] = [
    iLat,
    iLon,
    iKnot,
    iHeading,
  ].map((i) => toNumber(own[i]));
  if (![ownLat, ownLon, ownKnot, ownHeading].every(Number.isFinite))
    return rows;
  const [ownEast, ownNorth] = velocityEastNorth(ownKnot, ownHeading);

  // 표는 헤더 위치로 셀을 읽는다 — 행을 헤더 길이에 맞춘 뒤(짧으면 채우고 길면 자름,
  // 헤더 밖 셀은 원래도 표에 안 나온다) 새 열을 붙여야 값이 제 열에 온다.
  const fitted = (row) =>
    row.length >= head.length
      ? row.slice(0, head.length)
      : [...row, ...Array(head.length - row.length).fill('')];
  const extended = body.map((row) => {
    if (!Array.isArray(row)) return row;
    if (toNumber(row[iOwn]) === 1) return [...fitted(row), '0.0000', '0.00'];
    const [lat, lon, knot, heading] = [iLat, iLon, iKnot, iHeading].map((i) =>
      toNumber(row[i]),
    );
    if (![lat, lon, knot, heading].every(Number.isFinite)) {
      return [...fitted(row), '-', '-'];
    }
    const posEast =
      toRadians(lon - ownLon) * Math.cos(toRadians(ownLat)) * EARTH_RADIUS_M;
    const posNorth = toRadians(lat - ownLat) * EARTH_RADIUS_M;
    const [targetEast, targetNorth] = velocityEastNorth(knot, heading);
    const velEast = targetEast - ownEast;
    const velNorth = targetNorth - ownNorth;
    return [
      ...fitted(row),
      computeCpaNauticalMiles(posEast, posNorth, velEast, velNorth).toFixed(4),
      computeTcpaSeconds(posEast, posNorth, velEast, velNorth).toFixed(2),
    ];
  });
  return [[...rows[0], 'cpa', 'tcpa'], ...extended];
};

// csv_rows(2D: 헤더+행) → 이미지 위에 그릴 타선 박스. 좌표는 원본 이미지 픽셀(실측 1920×1080).
// 자선(my_ship=1)은 카메라 자신이라 화면에 없고 bbox 가 0 으로 채워져 있어 건너뛴다.
// bbox 열이 없으면 [] — 호출부가 오버레이 자체를 생략한다(일반 데이터셋 graceful).
export const extractShipBoxes = (rows) => {
  if (!Array.isArray(rows) || rows.length < 2 || !Array.isArray(rows[0])) return [];
  const head = rows[0].map(normalize);
  const at = (name) => head.indexOf(name);
  const [ix, iy, iw, ih] = ['bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'].map(at);
  if (ix < 0 || iy < 0 || iw < 0 || ih < 0) return [];
  const iOwn = at('my_ship');
  const iId = at('ship_id');
  const boxes = [];
  rows.slice(1).forEach((row, rowIndex) => {
    if (!Array.isArray(row)) return;
    if (iOwn >= 0 && toNumber(row[iOwn]) === 1) return;
    const [x, y, w, h] = [ix, iy, iw, ih].map((i) => toNumber(row[i]));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !(w > 0) || !(h > 0)) return;
    boxes.push({
      key: `row-${rowIndex}`,
      shipId: iId >= 0 ? String(row[iId] ?? '').trim() : '',
      x,
      y,
      w,
      h,
    });
  });
  return boxes;
};
