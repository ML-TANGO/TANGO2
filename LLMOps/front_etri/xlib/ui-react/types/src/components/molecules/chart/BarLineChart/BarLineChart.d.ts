import { BarLineChartData } from './types';
declare type Props = {
    data?: BarLineChartData;
    width?: number;
    height?: number;
    minXAxis?: number;
    minYAxis?: number;
    maxXAxis?: number;
    maxYAxis?: number;
    unitsPerTickX?: number;
    unitsPerTickY?: number;
    axisColor?: string;
    point?: number;
    barWidth?: number;
    lineChartColor?: string;
    barChartColor?: string;
    drawXAxis?: boolean;
    drawXValue?: boolean;
    drawXTick?: boolean;
    drawYAxis?: boolean;
    drawYValue?: boolean;
    drawYTick?: boolean;
    activeTooltip?: boolean;
    tooltipStyle?: {
        [key: string]: string;
    };
    isAxisDraw?: boolean;
    background?: string;
};
declare function BarLineChart({ data, width, height, minXAxis, minYAxis, maxXAxis, maxYAxis, unitsPerTickX, unitsPerTickY, axisColor, point, barWidth, lineChartColor, barChartColor, drawXAxis, drawXValue, drawXTick, drawYAxis, drawYValue, drawYTick, activeTooltip, tooltipStyle, isAxisDraw, background, }: Props): JSX.Element;
declare namespace BarLineChart {
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
        point: undefined;
        barWidth: undefined;
        lineChartColor: undefined;
        barChartColor: undefined;
        drawXAxis: undefined;
        drawXValue: undefined;
        drawXTick: undefined;
        drawYAxis: undefined;
        drawYValue: undefined;
        drawYTick: undefined;
        activeTooltip: undefined;
        tooltipStyle: undefined;
        isAxisDraw: undefined;
        background: undefined;
    };
}
export default BarLineChart;
