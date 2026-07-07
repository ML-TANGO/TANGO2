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
const CsvTable = ({ rows, text }) => {
  const data = Array.isArray(rows) && rows.length > 0 ? rows : parseCsv(text);
  if (!data || data.length === 0) return null;
  const [head, ...body] = data;

  return (
    <div className={cx('csv-wrap')}>
      <table className={cx('csv-table')}>
        <thead>
          <tr>
            {(head || []).map((cell, i) => (
              <th key={i}>{cell}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, r) => (
            <tr key={r} className={cx(r % 2 === 1 && 'csv-row--alt')}>
              {row.map((cell, i) => (
                <td key={i}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default CsvTable;
