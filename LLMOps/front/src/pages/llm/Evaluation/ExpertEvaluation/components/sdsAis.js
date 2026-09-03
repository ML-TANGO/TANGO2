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

// tcpa 원본 단위는 **초**다 — 같은 값이 생성 프롬프트에도 "TCPA:307.87초" 로 실린다.
// 헤더는 분으로 읽히므로 표시할 때 60 으로 나눈다. 안 나누면 307 을 307분(5시간)으로 읽어
// 조우 임박 상황을 여유 있는 상황으로 오판한다 — 충돌회피 채점에서 제일 위험한 오독이다.
// (원본 CSV 는 손대지 않는다. 표시 전용 변환.)
const TCPA_SECONDS_PER_MINUTE = 60;

// 표 셀 표시값. 0/1 코드·초 단위처럼 그대로 두면 오독되는 값만 바꾼다(원본 CSV 불변).
export const aisCellText = (t, cell, value) => {
  const col = normalize(cell);
  if (col === 'my_ship') {
    const code = toNumber(value);
    if (code === 1) return t('evaluation.expert.ais.own');
    if (code === 0) return t('evaluation.expert.ais.other');
    return value;
  }
  if (col === 'tcpa') {
    const seconds = toNumber(value);
    if (!Number.isFinite(seconds)) return value;
    return (seconds / TCPA_SECONDS_PER_MINUTE).toFixed(1);
  }
  return value;
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
