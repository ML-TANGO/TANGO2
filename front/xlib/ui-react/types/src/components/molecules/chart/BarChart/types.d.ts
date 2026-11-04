interface DataElement {
    value: number;
    color?: string;
}
interface DataType {
    data: number | DataElement;
    maxValue?: number;
    minValue?: number;
    xAxisData?: number;
}
interface BarChartData {
    xAxisSelector?: string;
    dataSelector?: string;
    data: DataType[] | Array<any>;
}
interface DrawParam {
    drawXAxis?: boolean;
    drawXValue?: boolean;
    drawXTick?: boolean;
    drawYAxis?: boolean;
    drawYValue?: boolean;
    drawYTick?: boolean;
}
interface BarChartArgs extends DrawParam {
    canvas: HTMLCanvasElement;
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
    background?: string;
}
export { DataType, BarChartArgs, BarChartData, DrawParam, DataElement };
