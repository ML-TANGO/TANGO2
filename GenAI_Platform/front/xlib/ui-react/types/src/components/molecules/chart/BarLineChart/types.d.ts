export interface DataType {
    lineData: number;
    barData: number;
    xAxisData?: number;
}
export interface BarLineChartData {
    xAxisSelector?: string;
    lineDataSelector?: string;
    barDataSelector?: string;
    data: DataType[] | Array<any>;
}
export interface DrawParam {
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
export interface BarLineChartArgs extends DrawParam {
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
    isAxisDraw?: boolean;
    hover?: boolean;
    hoverStyle?: 'red' | 'blue' | 'green';
    background?: string;
}
