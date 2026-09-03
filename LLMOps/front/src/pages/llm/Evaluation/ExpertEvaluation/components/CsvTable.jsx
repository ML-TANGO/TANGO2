import BorderTable from '@src/components/molecules/BorderTable';

import { aisCellText, aisColumnLabel, isBboxColumn } from './sdsAis';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// csv_text 폴백 파서(BE 파싱 csv_rows 2D 우선). 간이 따옴표 필드 처리.
const parseCsv = (text) => {
  if (typeof text !== 'string' || !text.trim()) return [];
  return text
    .trim()
    .split(/\r?\n/)
    .map((line) => {
      const cells = [];
      let cur = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if (ch === '"') {
          if (inQuotes && line[i + 1] === '"') {
            cur += '"';
            i += 1;
          } else {
            inQuotes = !inQuotes;
          }
        } else if (ch === ',' && !inQuotes) {
          cells.push(cur);
          cur = '';
        } else {
          cur += ch;
        }
      }
      cells.push(cur);
      return cells;
    });
};

// per-sample CSV(input_data.csv) 을 줄무늬 테이블로. 첫 행 = 헤더.
// graceful(D5): 데이터 없으면 아무것도 렌더하지 않음(일반 텍스트 데이터셋).
//   SDS(AIS) 표는 헤더를 한글·단위로 바꾸고 바운딩박스 좌표 열은 숨긴다 — 채점자가 읽을 값이
//   아니고, 같은 정보를 이미지 위 박스·확대 크롭으로 본다(전문가 피드백). 열 규약은 sdsAis 참조.
//   AIS 가 아닌 CSV 는 헤더 이름이 규약에 없어 원래 이름·전체 열 그대로 나온다.
const CsvTable = ({ rows, text, t }) => {
  const data = Array.isArray(rows) && rows.length > 0 ? rows : parseCsv(text);
  if (!data || data.length === 0) return null;
  const [head, ...body] = data;
  // 원본 열 번호를 키로 유지 — 숨긴 열이 있어도 헤더/셀 짝이 어긋나지 않는다.
  const shown = (head || [])
    .map((cell, index) => ({ cell, index }))
    .filter(({ cell }) => !isBboxColumn(cell));
  const columns = shown.map(({ cell, index }) => ({
    name: aisColumnLabel(t, cell),
    selector: (row) => row[`column-${index}`],
    wrap: true,
  }));
  const tableData = body.map((row, rowIndex) =>
    shown.reduce(
      (item, { cell, index }) => ({
        ...item,
        [`column-${index}`]: aisCellText(t, cell, row[index]),
      }),
      { id: rowIndex },
    ),
  );

  return (
    <div className={cx('csv-wrap')}>
      <BorderTable
        columns={columns}
        data={tableData}
        loading={false}
        selectableRows={false}
        hideSearchBox
        hideButtons
        fixedHeader
        fixedHeaderScrollHeight='320px'
      />
    </div>
  );
};

export default CsvTable;
