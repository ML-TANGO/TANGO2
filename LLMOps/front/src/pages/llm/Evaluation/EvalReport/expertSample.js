import {
  aisCellText,
  aisColumnLabel,
  isBboxColumn,
  withCpaTcpa,
} from '../ExpertEvaluation/components/sdsAis';

// 리포트의 `expert-sample` 블록 — 전문가 샘플 1건의 이미지 참조와 센서(AIS) 표를 담은 한 줄
// JSON(BE report.py `_sample_media`). 서버만 이 블록을 쓸 수 있다: 모델 출력·코멘트는 언어 이름이
// 없는 코드 블록이나 이스케이프한 표 셀로만 실린다.
export const EXPERT_SAMPLE_LANG = 'expert-sample';

// 코드 블록 하나(여는 줄 길이와 같은 줄까지). 블록을 통째로 건너야 모델 출력·코멘트 블록 안에
// 적힌 같은 모양의 글을 우리 블록으로 잘못 보지 않는다.
const FENCE = /^(`{3,})([^\n]*)\n([\s\S]*?)\n\1$/gm;

export const parseExpertSample = (text) => {
  try {
    const raw = JSON.parse(text);
    return {
      modelId: raw.model_id,
      jobId: raw.job_id,
      idx: raw.idx,
      image: raw.image === true,
      name: raw.name || '',
      rows: Array.isArray(raw.rows) ? raw.rows : [],
    };
  } catch {
    return null;
  }
};

// 센서 표 — 채점 화면(CsvTable)과 같은 규약: 한글 열 이름·단위, 바운딩박스 좌표 열 숨김(이미지 위
// 박스로 본다), CPA·TCPA 열이 없으면 계산해 붙인다. AIS 가 아닌 CSV 는 원래 열 그대로.
export const sensorTable = (t, rows) => {
  const [head, ...body] = withCpaTcpa(rows);
  if (!Array.isArray(head)) return null;
  const shown = head
    .map((cell, index) => ({ cell, index }))
    .filter(({ cell }) => !isBboxColumn(cell));
  return {
    head: shown.map(({ cell }) => aisColumnLabel(t, cell)),
    body: body.filter(Array.isArray).map((row) =>
      shown.map(({ cell, index }) => aisCellText(t, cell, row[index]) ?? ''),
    ),
  };
};

const mdCell = (value) =>
  String(value)
    .replace(/\s*[\r\n]+\s*/g, ' ')
    .replace(/\\/g, '\\\\')
    .replace(/\|/g, '\\|');

const mdRow = (cells) => `| ${cells.map(mdCell).join(' | ')} |`;

// .md 다운로드용 — 화면이 그리는 블록을 이미지 파일 이름과 Markdown 표로 바꾼다.
export const toDownloadMarkdown = (t, markdown) =>
  markdown.replace(FENCE, (block, ticks, lang, text) => {
    const sample = lang === EXPERT_SAMPLE_LANG ? parseExpertSample(text) : null;
    if (!sample) return block;
    const parts = [];
    if (sample.name) {
      parts.push(`**${t('evaluation.report.image')}** ${mdCell(sample.name)}`);
    }
    const table = sensorTable(t, sample.rows);
    if (table) {
      parts.push(
        `**${t('evaluation.report.sensorData')}**`,
        [
          mdRow(table.head),
          `|${'---|'.repeat(table.head.length)}`,
          ...table.body.map(mdRow),
        ].join('\n'),
      );
    }
    return parts.join('\n\n');
  });
