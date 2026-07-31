import * as d3 from 'd3';

function convertData(data) {
  let total = 0;
  let tmpData = [...data]
    .map((d) => {
      total += d.value;
      const obj = {
        value: d.value,
        cumulative: total - d.value,
        label: d.label,
        color: d.color,
      };
      if (d.color) obj.color = d.color;
      return obj;
    })
    .filter((d) => d.value > 0);
  const percent = d3.scaleLinear().domain([0, total]).range([0, 100]);
  tmpData = tmpData.map((d) => ({ ...d, percent: percent(d.value) }));
  return { data: tmpData, total };
}

class SingleStackBarChart {
  container;

  chartData = [];

  chart;

  config = {
    width: 500,
    height: 100,
    barHeight: 50,
    colors: ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33'],
    f: d3.format('.1f'),
    margin: {
      top: 20,
      right: 10,
      bottom: 30,
      left: 10,
    },
    displayPercent: false,
  };

  selection;

  xAxis;

  minText;

  maxText;

  legend;

  constructor(container, chartData) {
    this.container = container;
    this.chartData = chartData;
    this.init();
  }

  init() {
    const { container, config } = this;
    const { width, height, margin, barHeight } = config;

    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;
    const halfBarHeight = barHeight / 2;

    // Legend init
    this.legendDraw(d3.select(container));

    this.chart = d3
      .select(container)
      .append('svg')
      .attr('preserveAspectRatio', 'xMinYMin meet')
      .attr('viewBox', [0, 0, width, height]);

    this.chart
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)
      .append('rect')
      .attr('class', 'rect-stacked')
      .attr('y', h / 2 - halfBarHeight)
      .attr('height', barHeight)
      .attr('width', w)
      .style('fill', '#ececec');

    // Axis
    this.xAxis = this.chart.append('g');
    // min
    this.minText = this.xAxis
      .append('text')
      .attr('x', 10)
      .attr('y', 12)
      .attr('fill', '#747474')
      .text(0);

    // max
    this.maxText = this.xAxis
      .append('text')
      .attr('text-anchor', 'end')
      .attr('x', w + 10)
      .attr('y', 12)
      .attr('fill', '#747474')
      .text(0);

    // graph init
    this.selection = this.chart
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    this.updateData(this.chartData);
  }

  legendDraw(ele) {
    const bullutStyle =
      'display: inline-block; width: 6px; height: 6px; border-radius: 3px; margin-right: 4px;';

    if (!this.legend) {
      this.legend = ele
        .append('div')
        .style('margin-bottom', '10px')
        .append('ul')
        .style('margin', 0)
        .style('padding', 0);
    }

    this.legend
      .selectAll('li')
      .data(this.chartData)
      .join('li')
      .style('display', 'flex')
      .style('justify-content', 'space-between')
      .style('align-items', 'center')
      .style('margin-right', '10px')
      .style('font-size', '12px')
      .html(
        (d) =>
          `
            <span style='flex: 1;'>
              <span class='bullet' style='background-color: ${d.color}; ${bullutStyle}'></span><span>${d.label}</span>
            </span>
            <span style='flex: 1;'>
              ${d.value}
            </span>
          `,
      );
  }

  updateData(chartData = []) {
    const { data, total } = convertData(chartData);
    this.chartData = chartData;
    const { config } = this;
    const { width, height, margin, barHeight, colors, f, displayPercent } =
      config;

    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;
    const halfBarHeight = barHeight / 2;
    const xScale = d3.scaleLinear().domain([0, total]).range([0, w]);

    this.maxText.text(total);

    // stack rect for each data value
    this.selection
      .selectAll('rect')
      .data(data)
      .join('rect')
      .attr('class', 'rect-stacked')
      .attr('x', (d) => xScale(d.cumulative))
      .attr('y', h / 2 - halfBarHeight)
      .attr('height', barHeight)
      .attr('width', (d) => xScale(d.value))
      .style('fill', (d, i) => d.color || colors[i]);

    // add values on bar
    this.selection
      .selectAll('.text-value')
      .data(data)
      .join('text')
      .attr('class', 'text-value')
      .attr('text-anchor', 'middle')
      .attr('x', (d) => xScale(d.cumulative) + xScale(d.value) / 2)
      .attr('y', h / 2 + 5)
      .text((d) => d.value);

    // add some labels for percentages
    if (displayPercent) {
      this.selection
        .selectAll('.text-percent')
        .data(data)
        .join('text')
        .attr('class', 'text-percent')
        .attr('text-anchor', 'middle')
        .attr('x', (d) => xScale(d.cumulative) + xScale(d.value) / 2)
        .attr('y', h / 2 - halfBarHeight * 1.1)
        .text((d) => `${f(d.percent)} %`);
    }

    // legend
    this.legendDraw(d3.select(this.container));

    // add the labels
    // this.selection
    //   .selectAll('.text-label')
    //   .data(data)
    //   .join('text')
    //   .attr('class', 'text-label')
    //   .attr('text-anchor', 'middle')
    //   .attr('x', (d) => xScale(d.cumulative) + xScale(d.value) / 2)
    //   .attr('y', h / 2 + halfBarHeight * 1.1 + 20)
    //   .style('fill', (d, i) => d.color || colors[i])
    //   .text((d) => d.label);
  }
}

export default SingleStackBarChart;
