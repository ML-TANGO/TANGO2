// CSS Module
import classNames from 'classnames/bind';
import style from './StorageNewTemplate.module.scss';

const cx = classNames.bind(style);

const noop = () => 'Empty';

/**
 * 노드 페이지 대시보드 영역 템플릿 컴포넌트
 * @param {{
 *  pieChartRender: () => JSX.Element,
 *  stackBarChartRender: () => JSX.Element,
 *  tableRender: () => JSX.Element,
 * }} props
 */
function StorageNewTemplate({
  pieChartRender = noop,
  stackBarChartRender,
  listRender = noop,
  isFirstContainer,
}) {
  return (
    <div
      className={cx(
        'node-dashboard-template',
        stackBarChartRender && 'has-stack-bar',
        isFirstContainer ? 'top' : 'bottom',
      )}
    >
      <div className={cx('pie-chart-box')}>{pieChartRender}</div>
      {stackBarChartRender && (
        <div className={cx('stack-bar-chart-box')}>{stackBarChartRender}</div>
      )}
      <div className={cx('table-box')}>{listRender}</div>
    </div>
  );
}

export default StorageNewTemplate;
