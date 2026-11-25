import { fetchExpertImageBlob } from '@src/apis/llm/evaluation';

import { extractShipBoxes } from '../ExpertEvaluation/components/sdsAis';

// 리포트에 넣을 샘플 이미지 — 원본(장당 약 2MB PNG)을 받아 선박 박스·ID 를 그려 JPEG 로 바꾼다.
// 세션 하나가 100장이라 원본 그대로는 PDF 가 200MB 가 되고(JPEG 는 장당 약 120KB), HTML 로 얹은
// 박스는 인쇄에서 어긋날 수 있어 그림에 직접 그린다.
const MAX_WIDTH = 1920;
const JPEG_QUALITY = 0.9;
// 한 번에 받는 장수 — 100장을 한꺼번에 던지면 다른 화면 요청이 밀린다.
const MAX_PARALLEL = 4;

// 박스·이름표는 채점 화면(BboxLayer)과 같은 규약 — 초록 테두리 + 박스 위 ID 이름표.
const BOX_COLOR = '#00ff00';
const LABEL_BACKGROUND = '#00cc00';
const LABEL_INSIDE_RATIO = 0.05; // 박스가 상단에 붙으면 이름표를 안쪽에

let running = 0;
const waiting = [];

const acquire = () =>
  new Promise((resolve) => {
    if (running < MAX_PARALLEL) {
      running += 1;
      resolve();
    } else {
      waiting.push(resolve);
    }
  });

const release = () => {
  const next = waiting.shift();
  if (next) next();
  else running -= 1;
};

const drawBoxes = (ctx, boxes, scale) => {
  const { width, height } = ctx.canvas;
  const fontSize = Math.round(width / 80);
  const labelHeight = Math.round(fontSize * 1.5);
  const padding = Math.round(fontSize / 2);
  ctx.lineWidth = Math.max(2, Math.round(width / 800));
  ctx.strokeStyle = BOX_COLOR;
  ctx.font = `bold ${fontSize}px sans-serif`;
  ctx.textBaseline = 'middle';
  boxes.forEach((box) => {
    const [x, y, w, h] = [box.x, box.y, box.w, box.h].map((v) => v * scale);
    ctx.strokeRect(x, y, w, h);
    const label = `ID:${box.shipId || '?'}`;
    const top = y / height < LABEL_INSIDE_RATIO ? y : y - labelHeight;
    ctx.fillStyle = LABEL_BACKGROUND;
    ctx.fillRect(x, top, ctx.measureText(label).width + padding * 2, labelHeight);
    ctx.fillStyle = '#000';
    ctx.fillText(label, x + padding, top + labelHeight / 2);
  });
};

const drawSample = async (blob, boxes) => {
  const bitmap = await createImageBitmap(blob);
  const scale = Math.min(1, MAX_WIDTH / bitmap.width);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff'; // JPEG 에는 투명이 없다
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  drawBoxes(ctx, boxes, scale);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (result) =>
        result ? resolve(result) : reject(new Error('image encode failed')),
      'image/jpeg',
      JPEG_QUALITY,
    );
  });
};

// → JPEG Blob. 차례를 기다리는 사이 리포트가 닫혔으면 받지 않는다.
const loadSampleImage = async (sample, isOpen) => {
  await acquire();
  try {
    if (!isOpen()) throw new Error('report closed');
    const blob = await fetchExpertImageBlob(
      sample.modelId,
      sample.jobId,
      sample.idx,
    );
    return await drawSample(blob, extractShipBoxes(sample.rows));
  } finally {
    release();
  }
};

// 닫은 뒤에도 잠시 두는 시간 — 인쇄 창을 준비하는 동안 모달을 닫아도 이미지가 깨지지 않게.
const REVOKE_DELAY_MS = 60 * 1000;

export const NO_IMAGES = { total: 0, done: 0, failed: 0 };

// 리포트 1건의 이미지 보관소 — 같은 샘플은 한 번만 받고 한 번만 센다. 모달을 최소화했다 펴면
// 블록이 모두 다시 마운트되므로, 블록이 아니라 리포트가 이미지를 갖고 있어야 한다.
// onChange 로 준비 상황({ total, done, failed })을 알린다.
export const createSampleImages = (onChange) => {
  const loading = new Map(); // `${jobId}/${idx}` → Promise<blob URL>
  const urls = [];
  let count = NO_IMAGES;
  let open = true;

  const report = (patch) => {
    if (!open) return;
    count = { ...count, ...patch };
    onChange(count);
  };

  const load = (sample) => {
    const key = `${sample.jobId}/${sample.idx}`;
    if (loading.has(key)) return loading.get(key);
    report({ total: count.total + 1 });
    const promise = loadSampleImage(sample, () => open).then((blob) => {
      const url = URL.createObjectURL(blob);
      urls.push(url);
      return url;
    });
    promise.then(
      () => report({ done: count.done + 1 }),
      () => report({ done: count.done + 1, failed: count.failed + 1 }),
    );
    loading.set(key, promise);
    return promise;
  };

  const close = () => {
    open = false;
    setTimeout(() => urls.forEach((url) => URL.revokeObjectURL(url)), REVOKE_DELAY_MS);
  };

  return { load, close };
};
