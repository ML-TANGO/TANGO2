// nivo chart
import { ResponsiveLine } from '@nivo/line';
import { memo } from 'react';

import classNames from 'classnames/bind';
import style from './DeployLineChart.module.scss';

const cx = classNames.bind(style);

function DeployLineChart({
  data,
  width = 380,
  height,
  enableGridX,
  enableGridY,
  filled = false,
  enableTootlip = undefined,
  pointSize = 3,
  margin = {
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
  },
  tooltipFontSize = 'medium',
}) {
  return data ? (
    <ResponsiveLine
      width={width}
      height={height}
      data={data.chartData}
      enableGridX={enableGridX}
      enableGridY={enableGridY}
      enableSlices={enableTootlip}
      animate={false}
      margin={margin}
      enableArea={filled}
      yScale={{
        type: 'linear',
        stacked: true,
        min: 0,
        max: data.max,
      }}
      curve='linear'
      pointSize={pointSize}
      pointLabelYOffset={0}
      sliceTooltip={({ slice }) => {
        if (!slice) return <></>;
        if (!slice.points) return <></>;
        if (!Array.isArray(slice.points)) return <></>;
        if (slice.points.length === 0) return <></>;
        if (!slice.points[0].data) return <></>;

        return (
          <div className={cx('tooltip', tooltipFontSize)}>
            {slice.points[0].serieId ?? ''} : {slice.points[0].data.y ?? ''}
          </div>
        );
      }}
    />
  ) : (
    <></>
  );
}

export default memo(DeployLineChart, (prev, next) => prev.data === next.data);
