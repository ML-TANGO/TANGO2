// CSS Module
import classNames from 'classnames/bind';
import style from './NodeStackBarChart.module.scss';
const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용되는 막대 차트 컴포넌트
 * @param {{
 *  data: [{ label: string, value: Number, total: number }]
 * }} props
 * @component
 * @example
 *
 * const data =[
 *  { label: 'A', value: 4, total: 10 },
 *  { label: 'B', value: 4, total: 10 },
 * ];
 *
 * return (
 *  <NodeStackBarChart data={data} />
 * );
 *
 */
function NodeStackBarChart({ data = [] }) {
  return (
    <div className={cx('node-stack-bar-chart')}>
      {data.map(({ label, value, total }, key) => {
        let rate = Math.floor((value / total) * 100);
        rate = Number.isNaN(rate) ? 0 : rate;
        return (
          <div key={key} className={cx('chart-item')}>
            <p className={cx('title')}>{label}</p>
            <div className={cx('stack-chart')}>
              <div className={cx('stack-info')}>
                <span>{`(${value}/${total})`}</span>
                <span>{`${rate}%`}</span>
              </div>
              <div className={cx('stack')}>
                <div className={cx('fill')} style={{ width: `${rate}%` }}></div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default NodeStackBarChart;
