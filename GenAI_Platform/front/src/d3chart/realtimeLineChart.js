import * as d3 from 'd3';

import './style.scss';

/**
 *
 * @param {Object} param 그래프 옵션
 * @param {string} param.eleId 차트렌더링을 위한 html id
 * @param {number} param.width 그래프 넓이
 * @param {number} param.height 그래프 높이
 * @param {boolean} param.legend 레전드 렌더링 여부
 * @param {'date' | undefined} param.scaleType x축 스케일 타입 지정
 * @property {function} draw 차트 렌더링 함수
 * @example
 *
 * const lineChart = new LineChart({
 *   eleId: 'line-chart', // 'line-chart' dom id
 *   width: 300, // 차트 넓이
 *   height: 200, // 차트 높이
 *   isResponsive: true, // 반응형 여부
 *   scaleType: 'date', // x축 스케일 타입 'date'
 *   legend: true, // 레전드 렌더링 여부
 *   xTickFormat: (ts) => dayjs.unix(ts).format('m:ss'), // x축 틱 라벨 포맷
 *   xAxisMaxTicks: 6, // x축 틱 갯수
 *   tooltip: {
 *     align: 'right' // 툴팁 align
 *   }
 * });
 *
 */
export default function LineChart({
  data: _d,
  eleId: _id,
  width: _w,
  height: _h,
  legend: _l,
  scaleType: _scaleType,
  xTickFormat: _xTickFormat,
  xAxisMaxTicks: _xAxisMaxTicks,
  yAxisMaxTicks: _yAxisMaxTicks,
  tooltip: _tooltip,
}) {
  this.eleId = _id;
  this.width = _w || 950;
  this.height = _h || 500;
  this.margin = {
    top: 20,
    right: 40,
    bottom: 50,
    left: 40,
  };
  this.tooltipInfo = _tooltip;
  this.scaleType = _scaleType;
  this.xTickFormat = _xTickFormat;
  this.xAxisMaxTicks = _xAxisMaxTicks || 10;
  this.yAxisMaxTicks = _yAxisMaxTicks || 10;

  this.series = [];
  this.data = _d || [];
  this.xAxis = undefined;
  this.yAxisArr = [];
  this.xScale = undefined;
  this.legendEle = undefined;

  this.chart = undefined;
  this.legend = _l;
  this.tooltip = undefined;
  this.tooltipLine = undefined;
  this.boxForTooltipMove = undefined;

  this.init = (data) => {
    this.data = data || [];
    const { eleId, width, height } = this;

    this.chart = d3
      .select(`#${eleId}`)
      .attr('class', 'chart-container')
      .append('svg')
      .attr('preserveAspectRatio', 'xMinYMin meet')
      .attr('viewBox', [0, 0, width, height])
      .append('g');

    // 툴팁 init
    this.tooltip = d3
      .select('body')
      .append('div')
      .attr('class', 'tooltip')
      .style('position', 'absolute')
      .style('top', '0px')
      .style('left', '0px');

    // 툴팁 라인 init
    this.tooltipLine = this.chart.append('line');

    // 툴팁을 위한 마우스 오버 이벤트 박스
    this.boxForTooltipMove = this.chart.append('rect');
  };

  // 시리즈 추가
  this.addSeries = (item) => {
    const dot = this.chart
      .append('circle')
      .attr('r', 3)
      .attr('fill', item.color)
      .style('display', 'none');

    const path = this.chart.append('path');
    this.series.push({
      ...item,
      dot,
      path,
    });
  };

  // series 설정
  this.setSeries = (seriesArr) => {
    const { series, data, height } = this;
    for (let i = 0; i < this.yAxisArr.length; i += 1) {
      const yAxis = this.yAxisArr[i];
      yAxis.remove();
      // if (!seriesArr[i]) {
      // yAxis.remove();
      // }
    }
    this.yAxisArr = [];
    // this.yAxisArr = this.yAxisArr.slice(0, seriesArr.length);

    for (let i = 0; i < series.length; i += 1) {
      const { dot, path } = series[i];
      dot.remove();
      path.remove();
    }
    this.series = seriesArr.map((item) => {
      const dot = this.chart
        .append('circle')
        .attr('r', 3)
        .attr('fill', item.color)
        .style('display', 'none');

      const path = this.chart.append('path');

      const yScale = d3
        .scaleLinear()
        .domain(d3.extent(data, (d) => d[item.x]))
        .range([height, 0]);

      return {
        ...item,
        dot,
        path,
        yScale,
      };
    });
  };

  // 그래프 렌더링

  /**
   * 차트 렌더링 함수
   * @param {Array} d 렌더링할 데이터(배열) 데이터의 정렬은 오름차순으로 보내야함
   */
  this.draw = (d) => {
    if (d) this.data = d;
    const { series, margin } = this;
    const { w, h, leftXPos, xTarget } = this.getChartAreaInfo(series);

    // 그래프 영역 위치 조정
    this.chart.attr('transform', `translate(${leftXPos}, ${margin.top})`);

    // x축 렌더링
    this.renderXAxis(this.data, w, h, xTarget);

    // path, y축 렌더링
    this.renderYAxisAndPath(series, this.data, h);

    // 레전드 렌더링
    if (this.legend) this.renderLegend(d3.select(`#${this.eleId}`), series);

    // 툴팁 렌더링
    this.renderTooltip(w, h, xTarget);
  };

  // x축 렌더링
  this.renderXAxis = (d, w, h, xTarget) => {
    const { scaleType } = this;

    if (scaleType === 'date') {
      this.xScale = d3
        .scaleTime()
        .domain(d3.extent(d, (data) => data[xTarget]))
        .range([0, w]);
    } else {
      this.xScale = d3
        .scaleLinear()
        .domain(d3.extent(d, (data) => data[xTarget]))
        .range([0, w]);
    }
    if (!this.xAxis) {
      this.xAxis = this.chart
        .append('g')
        .attr('class', 'xaxis')
        .attr('transform', `translate(0, ${h})`)
        .style('color', '#3e3e3e')
        .call(
          d3
            .axisBottom(this.xScale)
            .ticks(this.getTick(d))
            .tickFormat((v) => {
              if (this.xTickFormat) return this.xTickFormat(v);
              return v;
            }),
        );
    } else {
      this.xAxis
        .transition()
        .duration(500)
        .ease(d3.easeLinear)
        .call(
          d3
            .axisBottom(this.xScale)
            .ticks(this.getTick(d))
            .tickFormat((v) => {
              if (this.xTickFormat) return this.xTickFormat(v);
              return v;
            }),
        );
    }
  };

  // Y축 및 라인 렌더링
  this.renderYAxisAndPath = (series, d, h) => {
    const { yAxisArr, width, margin, data } = this;
    let leftX = 0;
    let rightX = 0;
    this.series = series.map((sVal, i) => {
      const { y, align, color, domain = [] } = sVal;
      // Add Y axis
      const yAxis = yAxisArr[i];

      const [min, max] = domain;
      const dataMax = d3.max(d, (item) => item[y]);
      const scaleDomain = [
        min !== undefined && min < 0 ? min : 0,
        max !== undefined && max > dataMax ? max : dataMax,
      ];

      const yScale = d3.scaleLinear().domain(scaleDomain).range([h, 0]);
      if (align === 'LEFT') {
        leftX = margin.left * i * -1;
        this.renderYAxis(yAxis, leftX, align, yScale, color, y);
      } else {
        rightX = width - margin.right * (i + 1);
        this.renderYAxis(yAxis, rightX, align, yScale, color, y);
      }

      this.renderPath(series[i], yScale, data);
      return { ...sVal, yScale };
    });
    // for (let i = 0; i < series.length; i += 1) {
    //   const yAxis = yAxisArr[i];
    //   const { y, align, color } = series[i];
    //   // Add Y axis
    //   const yScale = d3.scaleLinear()
    //     .domain([0, d3.max(d, (item) => item[y])])
    //     .range([ h, 0 ]);

    //   if (align === 'LEFT') {
    //     leftX = margin.left * i * -1;
    //     this.renderYAxis(yAxis, leftX, align, yScale, color, y);
    //   } else {
    //     rightX = width - margin.right * (i + 1);
    //     this.renderYAxis(yAxis, rightX, align, yScale, color, y);
    //   }

    //   this.renderPath(series[i], paths[i], yScale, data);
    // }
  };

  // y축 렌더링
  this.renderYAxis = (yAxis, xPos, align, yScale, color) => {
    const { yAxisArr } = this;
    if (!yAxis) {
      const axis = this.chart
        .append('g')
        .attr('class', `yaxis ${align}`)
        .attr('transform', `translate(${xPos}, 0)`)
        .call(align === 'LEFT' ? d3.axisLeft(yScale) : d3.axisRight(yScale))
        .call((tmpG) => tmpG.select('.domain').style('display', 'none'));
      yAxisArr.push(axis);
      axis.selectAll('text').style('fill', color);
      axis.selectAll('line').style('stroke', color);
    } else {
      yAxis
        .attr('class', `yaxis ${align}`)
        .attr('transform', `translate(${xPos}, 0)`)
        .transition()
        .duration(500)
        .ease(d3.easeLinear)
        .call(align === 'LEFT' ? d3.axisLeft(yScale) : d3.axisRight(yScale));

      yAxis.selectAll('text').style('fill', color);

      yAxis.selectAll('line').style('stroke', color);
    }
  };

  // 라인 렌더링
  this.renderPath = (s, yScale, data) => {
    const { x, y, color, path } = s;
    // 7. d3's line generator
    const line = d3
      .line()
      // .curve(d3.curveBasis)
      .x((d) => this.xScale(d[x])) // set the x values for the line generator
      .y((d) => yScale(d[y])); // set the y values for the line generator
    // .curve(d3.curveMonotoneX) // apply smoothing to the line

    path
      .datum(data) // 10. Binds data to the line
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 1)
      // .attr('stroke-linejoin', 'round')
      // .attr('stroke-linecap', 'round')
      .attr('class', 'line') // Assign a class for styling
      .attr('d', line); // 11. Calls the line generator
  };

  // 레전드 렌더링
  this.renderLegend = (ele, series) => {
    if (!this.legendEle) {
      this.legendEle = ele
        .append('div')
        .attr('class', 'legend-wrap')
        .append('ul')
        .attr('class', 'legend');
    }
    this.legendEle
      .selectAll('li')
      .data(series)
      .join('li')
      .html(
        (d) =>
          `<span class='bullet' style='background-color: ${
            d.color
          }'></span><span>${d.label || d.y}</span>`,
      );
  };

  // 그래프 영역 정보 가져오기
  this.getChartAreaInfo = (series) => {
    const { width, margin } = this;
    let leftAxisCount = 0;
    let rightAxisCount = 0;
    let xTarget;
    for (let i = 0; i < series.length; i += 1) {
      const { align, x } = series[i];
      if (x) xTarget = x;
      if (align === 'RIGHT') {
        rightAxisCount += 1;
      } else {
        leftAxisCount += 1;
      }
    }
    leftAxisCount = Math.max(leftAxisCount, 1);
    rightAxisCount = Math.max(rightAxisCount, 1);
    const leftXPos = margin.left * leftAxisCount;
    const rightXPos = margin.right * rightAxisCount;
    return {
      w: width - leftXPos - rightXPos,
      h: this.getViewHeight(),
      leftXPos,
      rightXPos,
      xTarget,
    };
  };

  // 툴팁 렌더링
  this.renderTooltip = (w, h, xTarget) => {
    this.boxForTooltipMove
      .raise()
      .attr('width', w + 10)
      .attr('height', h)
      .attr('fill-opacity', 0)
      .attr('class', 'zoom')
      .on('mousemove', () => {
        this.drawTooltip(w, h, xTarget);
      })
      .on('mouseout', this.removeTooltip);
  };

  this.drawTooltip = (w, h, xTarget) => {
    const { series, data, tooltipInfo, xTickFormat } = this;

    // return;
    const bisect = d3.bisector((d) => {
      return d[xTarget];
    }).left;

    const [xPos] = d3.mouse(this.boxForTooltipMove.node());
    const xVal = Math.round(this.xScale.invert(xPos));

    const i = bisect(data, xVal);

    const targetData = data[i];
    if (targetData === undefined) return;
    for (let idx = 0; idx < series.length; idx += 1) {
      const { x, y, yScale, dot } = series[idx];
      const dotX = this.xScale(targetData[x]);
      const dotY = yScale(targetData[y]);
      dot
        .style('display', 'block')
        .transition()
        .duration(100)
        .ease(d3.easeLinear)
        .attr('transform', `translate(${dotX},${dotY})`);

      this.tooltipLine
        .attr('stroke', '#3e3e3e')
        .style('stroke-dasharray', '3, 3')
        .transition()
        .duration(100)
        .ease(d3.easeLinear)
        .attr('x1', dotX)
        .attr('x2', dotX)
        .attr('y1', 0)
        .attr('y2', h);
    }

    const top = d3.event.pageY - 20;
    let left = d3.event.pageX + 20;
    if (tooltipInfo && tooltipInfo.align && tooltipInfo.align === 'right') {
      left = d3.event.pageX - 200;
    }

    this.tooltip
      .html(xTickFormat ? xTickFormat(xVal) : xVal)
      .style('display', 'block')
      .style('width', '160px')
      .style('min-width', 'fit-content')
      .style('border', '1px solid #ccc')
      .style('padding', '10px')
      .style('background', '#ffffff')
      .style('top', `${top}px`)
      .style('left', `${left}px`)
      .selectAll('div')
      .data(series)
      .join('div')
      .html(({ y, label }) => `${label || y} : ${targetData[y]}`)
      .style('font-size', '11px')
      .style('margin-bottom', '4px')
      .style('color', (d) => d.color);
  };

  this.removeTooltip = () => {
    const { tooltip, tooltipLine, series } = this;
    if (tooltip) tooltip.style('display', 'none');
    if (tooltipLine) tooltipLine.attr('stroke', 'none');
    for (let i = 0; i < series.length; i += 1) {
      const { dot } = series[i];
      dot.style('display', 'none');
    }
  };

  // // 데이터 업데이트
  // this.updateData = (d) => {
  //   this.data = d;
  // }

  this.getViewWidth = () => this.width - this.margin.left - this.margin.right;
  this.getViewHeight = () => this.height - this.margin.top - this.margin.bottom;
  this.getTick = (data) => {
    const { xAxisMaxTicks } = this;
    const dataLength = data.length;
    if (xAxisMaxTicks) {
      return dataLength < xAxisMaxTicks ? dataLength : xAxisMaxTicks;
    }
    return dataLength;
  };

  this.init();
}

// const chart = new LineChart({
//   eleId: 'line-chart',
//   width: 500,
//   height: 300,
//   legend: true
// });

// chart.addSeries({
//   align: 'LEFT',
//   x: 'year',
//   y: 'popularity',
//   color: '#e57373',
// });
// chart.addSeries({
//   align: 'LEFT',
//   x: 'year',
//   y: 'a',
//   color: '#ba68c8',
// });
// chart.addSeries({
//   align: 'RIGHT',
//   x: 'year',
//   y: 'b',
//   color: '#7986cb',
// });

// chart.addSeries({
//   align: 'RIGHT',
//   x: 'year',
//   y: 'c',
//   color: '#4fc3f7',
// });

// 4db6ac, aed581, fff176, ffb74d, ff8a65

// chart.draw();
// chart.draw(data);

// let count = 0;
// setInterval(() => {
//   count += 1;
//   chart.draw(data.slice(0, count));
// }, 1000);
