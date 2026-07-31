// Components
import DeployLineChart from '@src/components/molecules/DeployChart/DeployLineChart/DeployLineChart';

// CSS Module
import classNames from 'classnames/bind';
import style from './OverviewGPUChart.module.scss';
const cx = classNames.bind(style);

function WorkerListOverviewChart({ gpuGraphData, t }) {
  return (
    <ul className={cx('overview-chart', 'gpu')}>
      {gpuGraphData.map((gpu, idx) => {
        const {
          gpuUtil,
          totalMemory,
          usedMemory,
          usedMemoryRatio,
          gpuChart,
          memChart,
        } = gpu;
        return (
          <li key={`${idx}-`} className={cx('gpu-chart')}>
            <div className={cx('chart-label')}>
              <label>GPU-{idx + 1}</label>
              <label>{t('last5m.label')}</label>
            </div>
            <div className={cx('charts')}>
              <div>
                <label>
                  Util : <span className={cx('value')}>{gpuUtil}%</span>
                </label>
                <div className={cx('chart-area')}>
                  <DeployLineChart
                    data={gpuChart}
                    height={161}
                    enableGridX={false}
                    enableGridY={false}
                    filled={true}
                  />
                </div>
              </div>
              <div>
                <label>
                  MEM :{' '}
                  <span className={cx('value')}>
                    {usedMemoryRatio} ({usedMemory} / {totalMemory} MiB)
                  </span>
                </label>
                <div className={cx('chart-area')}>
                  <DeployLineChart
                    data={memChart}
                    height={161}
                    enableGridX={false}
                    enableGridY={false}
                    filled={true}
                  />
                </div>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default WorkerListOverviewChart;
