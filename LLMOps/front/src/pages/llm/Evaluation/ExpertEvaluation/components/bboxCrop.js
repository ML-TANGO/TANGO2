// 확대 크롭 — 원본 1920×1080 안에서 타선은 작게는 20px, 크게는 500px 로 편차가 커서 인라인
// 이미지 하나로는 어느 쪽도 제대로 못 본다(작으면 안 보이고, 크면 다른 배와 섞인다). 배마다
// 박스 + 주변 여백을 잘라 같은 크기 패널에 꽉 채운다 — 어느 샘플이든 배가 비슷한 크기로 보인다.
//   ⚠️ 확대율에 하한 1배를 걸면 안 된다. 패널보다 큰 박스(실측 530×460)가 잘려 뱃머리/선미가
//   패널 밖으로 나간다 — 판독하라고 만든 화면에서 정작 배가 잘리는 게 제일 나쁘다.
export const CROP_W = 420;
export const CROP_H = 290;
const CROP_CONTEXT = 1.5; // 박스 대비 크롭 영역 배수(주변 바다·수평선이 같이 보여야 판단이 선다)
const CROP_MIN_ZOOM = 0.05;
const CROP_MAX_ZOOM = 8; // 그 위로는 없는 정보 없이 보간 뭉개짐만 커진다
const CROP_MAX_COUNT = 8; // 표에 배가 많아도 대형 이미지 N 개를 한 화면에 띄우지 않는다
// 이 배 이상일 때만 "확대 N배" 를 적는다 — 큰 박스는 축소해 담기므로 배율을 쓰면 거짓말이 된다.
export const CROP_ZOOM_LABEL_MIN = 1.05;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

// 박스 목록 → 패널 목록(확대율·크롭 원점 포함). 원본 크기를 알아야 계산되므로 로드 후에만 부른다.
export const buildCrops = (boxes, natWidth, natHeight, colors) =>
  boxes.slice(0, CROP_MAX_COUNT).map((box, index) => {
    // 박스+여백이 패널에 통째로 들어가는 배율 — 가로/세로 중 빡빡한 쪽에 맞춘다.
    const zoom = clamp(
      Math.min(CROP_W / (box.w * CROP_CONTEXT), CROP_H / (box.h * CROP_CONTEXT)),
      CROP_MIN_ZOOM,
      CROP_MAX_ZOOM,
    );
    const viewW = Math.min(CROP_W / zoom, natWidth);
    const viewH = Math.min(CROP_H / zoom, natHeight);
    // 박스를 패널 한가운데 두되, 이미지 가장자리 배는 크롭이 밖으로 나가지 않게 안으로 민다.
    const originX = clamp(
      box.x + box.w / 2 - viewW / 2,
      0,
      Math.max(0, natWidth - viewW),
    );
    const originY = clamp(
      box.y + box.h / 2 - viewH / 2,
      0,
      Math.max(0, natHeight - viewH),
    );
    return {
      ...box,
      index: index + 1,
      color: colors[index % colors.length],
      zoom,
      originX,
      originY,
      viewW,
      viewH,
    };
  });

export const cropsOmitted = (boxes) => Math.max(0, boxes.length - CROP_MAX_COUNT);
