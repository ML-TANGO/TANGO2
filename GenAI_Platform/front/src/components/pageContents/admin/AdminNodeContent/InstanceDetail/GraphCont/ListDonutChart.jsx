import * as d3 from 'd3';
import React, { useEffect, useRef, useState } from 'react';

import { calAllocateInstanceValue } from '../InstanceDetail';

import classNames from 'classnames/bind';
import style from './GraphCont.module.scss';

const cx = classNames.bind(style);

export const calInstanceName = (instanceInfo) => {
  if (!instanceInfo) return '';
  return instanceInfo.gpu_name === 'No Resource Group'
    ? `CPU.${instanceInfo.cpu_count}.${instanceInfo.ram_count}`
    : instanceInfo.gpu_name;
};

const ListDonutChart = React.memo(
  ({ data, percentage, width, instanceTotalValue }) => {
    const svgRef = useRef();
    const [tooltip, setTooltip] = useState({
      visible: false,
      content: {
        header: {
          name: '',
          allocateValue: 0,
          totalValue: 0,
        },
        vGpu: 0,
        vCpu: 0,
        ram: 0,
      },
      x: 0,
      y: 0,
    });
    const { visible, content } = tooltip;
    const { header, vGpu, vCpu, ram } = content;
    const { name, allocateValue, totalValue } = header;

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
        .attr('style', 'max-width: 100%; height: auto;');

      svg
        .append('g')
        .selectAll()
        .data(pie(data))
        .join('path')
        .attr('fill', (d) => {
          return !d.data.color ? 'transparent' : d.data.color;
        })
        .attr('d', arc)
        .on('mouseover', (event) => {
          const centroid = arc.centroid(event); // 세그먼트의 중심점을 계산
          const name = calInstanceName(event.data);
          const { allocate_workspace_list, cpu_count, gpu_count, ram_count } =
            event.data;

          const allocateValue = calAllocateInstanceValue(
            allocate_workspace_list,
          );
          setTooltip({
            visible: !!name,
            content: {
              header: {
                name,
                allocateValue: allocateValue,
                totalValue: instanceTotalValue,
              },
              vGpu: gpu_count,
              vCpu: cpu_count,
              ram: ram_count,
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
              header: {
                name: '',
                allocateValue: 0,
                totalValue: 0,
              },
              vGpu: 0,
              vCpu: 0,
              ram: 0,
            },
            x: 0,
            y: 0,
          });
        });
    }, [data, instanceTotalValue, width]);

    return (
      <div className={cx('dounut')}>
        <svg ref={svgRef}></svg>
        <span className={cx('percent-txt')}>{percentage}%</span>
        {visible && (
          <div
            className={cx('tooltip')}
            style={{
              position: 'absolute',
              top: `${tooltip.y}px`,
              left: tooltip.x,
            }}
          >
            <div className={cx('header')}>
              <span className={cx('instance-name-txt')}>{name}</span>
              <span className={cx('value')}>{allocateValue}</span>
              <span>EA</span>
              <span>/</span>
              <span className={cx('value')}>{totalValue}</span>
              <span>EA</span>
            </div>
            <div className={cx('content')}>
              <div className={cx('flex-row')}>
                <span className={cx('label')}>vGPU</span>
                <span className={cx('value')}>{vGpu} EA</span>
              </div>
              <div className={cx('flex-row')}>
                <span className={cx('label')}>vCPU</span>
                <span className={cx('value')}>{vCpu} Cores</span>
              </div>
              <div className={cx('flex-row')}>
                <span className={cx('label')}>RAM</span>
                <span className={cx('value')}>{ram} GB</span>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  },
);

export default ListDonutChart;
