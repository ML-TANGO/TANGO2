import { BarLineChartParam, DrawParam } from './BarLineChartTypes';
/**
 * Bar차트 Line차트를 생성하는 class
 * 단순 for loop 알고리즘 개선 필요 O(N) => O(logN)
 * tooltip 기능 추가 필요
 */
declare class BarLineChart {
    private canvas;
    private ctx;
    private tooltip;
    private data;
    private minXAxis;
    private minYAxis;
    private maxXAxis;
    private maxYAxis;
    private minMax;
    private unitsPerTickX;
    private unitsPerTickY;
    private padding;
    private tickSize;
    private axisColor;
    private pointRadius;
    private font;
    private fontHeight;
    private rangeX;
    private rangeY;
    private numXTicks;
    private numYTicks;
    private x;
    private y;
    private width;
    private height;
    private scaleX;
    private scaleY;
    private xAxisSelector;
    private lineDataSelector;
    private barDataSelector;
    private barWidth;
    private lineChartColor;
    private barChartColor;
    private isAxisDraw;
    private start;
    constructor(param: BarLineChartParam);
    private minAndMax;
    private getLongestValueWidth;
    private calcRelation;
    private drawXAxis;
    private drawXTick;
    private drawXValue;
    private drawYAxis;
    private drawYTick;
    private drawYValue;
    private drawChart;
    private tooltipMaker;
    private drawTooltip;
    draw(draw?: DrawParam): void;
}
export default BarLineChart;
