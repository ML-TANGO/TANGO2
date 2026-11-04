import * as d3 from 'd3';
import React, { useEffect, useRef, useState } from 'react';

import classNames from 'classnames/bind';
import style from './ListDonut.module.scss';

const cx = classNames.bind(style);

export const calInstanceName = (instanceInfo) => {
  if (!instanceInfo) return '';
  return instanceInfo.gpu_name === 'No Resource Group'
    ? `CPU.${instanceInfo.cpu_count}.${instanceInfo.ram_count}`
    : instanceInfo.gpu_name;
};

const ListDonut = React.memo(({ data, storageType, percentage, width }) => {
  const svgRef = useRef();
  const [tooltip, setTooltip] = useState({
    visible: false,
    content: {
      name: 'FlIGHTBASE',
      size: 0,
      status: '사용중',
    },
    x: 0,
    y: 0,
  });
  const { visible, content } = tooltip;
  const { name, size, status } = content;

  useEffect(() => {
    const height = Math.min(width, 500);
    const radius = Math.min(width, height) / 2;

    // 아크 생성기
    const arc = d3
      .arc()
      .innerRadius(radius * 0.8)
      .outerRadius(radius - 1);

    // 파이 생성기
    const pie = d3
      .pie()
      .padAngle(1 / radius)
      .sort(null)
      .value((d) => d.value);

    // SVG 컨테이너 생성
    const svg = d3
      .select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [-width / 2, -height / 2, width, height])
      .attr('stroke', 'none')
      .attr('style', 'max-width: 100%; height: auto;');

    svg
      .append('g')
      .selectAll()
      .data(pie(data))
      .join('path')
      .attr('stroke', 'none')
      .attr('fill', (d) => {
        return !d.data.color ? 'transparent' : d.data.color;
      })
      .attr('d', arc)
      .attr('stroke', 'none')
      .on('mouseover', (event) => {
        const centroid = arc.centroid(event); // 세그먼트의 중심점을 계산
        const { color, name, size, value } = event.data;

        setTooltip({
          visible: !!name,
          content: {
            name,
            size,
            status,
          },
          x: centroid[0], // 세그먼트 중심 X 좌표
          y: centroid[1] + 100, // 세그먼트 중심 Y 좌표 (위쪽으로 약간 이동)
        });
      })
      .on('mousemove', (event) => {
        const centroid = arc.centroid(event); // 세그먼트의 중심점
        setTooltip((prev) => ({
          ...prev,
          x: centroid[0],
          y: centroid[1] + 100, // 세그먼트 중심 Y 좌표 (위쪽으로 약간 이동)
        }));
      })
      .on('mouseleave', () => {
        setTooltip({
          visible: false,
          content: {
            name: '',
            size: 0,
            status: '',
          },
          x: 0,
          y: 0,
        });
      });
  }, [data, size, status, width]);

  return (
    <div className={cx('donut')}>
      <svg ref={svgRef}></svg>
      <div className={cx('text-cont')}>
        <span className={cx('datatype-txt')}>{storageType}</span>
        <span className={cx('percent-txt')}>{percentage}%</span>
      </div>
      {visible && (
        <div
          className={cx('tooltip')}
          style={{
            position: 'absolute',
            top: `${tooltip.y}px`,
            left: tooltip.x,
          }}
        >
          <span className={cx('name')}>{name}</span>
          <span className={cx('size')}>{size}</span>
          <span className={cx('status')}>사용중</span>
        </div>
      )}
    </div>
  );
});

export default ListDonut;
