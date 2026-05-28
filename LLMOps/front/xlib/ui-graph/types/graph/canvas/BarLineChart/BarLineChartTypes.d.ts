interface DataType {
    lineData: number;
    barData: number;
    xAxisData?: number;
}
interface BarLineChartData {
    xAxisSelector?: string;
    lineDataSelector?: string;
    barDataSelector?: string;
    data: DataType[] | Array<any>;
}
interface BarLineChartParam {
    canvas: HTMLCanvasElement;
    tooltip?: Element | null;
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
    background?: string;
    isAxisDraw?: boolean;
}
interface DrawParam {
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
}
export { BarLineChartParam, BarLineChartData, DataType, DrawParam };
