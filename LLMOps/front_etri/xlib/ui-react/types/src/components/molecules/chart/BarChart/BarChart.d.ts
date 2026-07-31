import { BarChartData } from './types';
declare type Props = {
    data?: BarChartData;
    width?: number;
    height?: number;
    minXAxis?: number;
    minYAxis?: number;
    maxXAxis?: number;
    maxYAxis?: number;
    unitsPerTickX?: number;
    unitsPerTickY?: number;
    axisColor?: string;
    barWidth?: number;
    barColor?: string;
    isAxisDraw?: boolean;
    drawXAxis?: boolean;
    drawXValue?: boolean;
    drawXTick?: boolean;
    drawYAxis?: boolean;
    drawYValue?: boolean;
    drawYTick?: boolean;
    background?: string;
};
declare function BarChart({ data, width, height, minXAxis, minYAxis, maxXAxis, maxYAxis, unitsPerTickX, unitsPerTickY, axisColor, barWidth, barColor, isAxisDraw, drawXAxis, drawXValue, drawXTick, drawYAxis, drawYValue, drawYTick, background, }: Props): JSX.Element;
declare namespace BarChart {
    var defaultProps: {
        data: never[];
        width: undefined;
        height: undefined;
        minXAxis: undefined;
        minYAxis: undefined;
        maxXAxis: undefined;
        maxYAxis: undefined;
        unitsPerTickX: undefined;
        unitsPerTickY: undefined;
        axisColor: undefined;
        barWidth: undefined;
        barColor: undefined;
        drawXAxis: undefined;
        drawXValue: undefined;
        drawXTick: undefined;
        drawYAxis: undefined;
        drawYValue: undefined;
        drawYTick: undefined;
        isAxisDraw: undefined;
        background: undefined;
    };
}
export default BarChart;
