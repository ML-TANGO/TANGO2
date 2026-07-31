interface SeriesType {
    name: string;
    series: number[];
    color?: string;
    lineWidth?: number;
}
interface AxisInfo {
    unitsPerTick?: number;
    max?: number;
    min?: number;
    padding?: number;
    tickSize?: number;
    tickColor?: string;
    lineWidth?: number;
    value?: number[];
    color?: string;
}
interface DataType {
    left: SeriesType[];
    bottom?: SeriesType[];
    right?: SeriesType[];
}
interface BottomAxisInfo extends AxisInfo {
    data?: number[] | string[];
}
interface RenderOption {
    bottomAxis?: boolean;
    bottomTick?: boolean;
    bottomText?: boolean;
    leftAxis?: boolean;
    leftTick?: boolean;
    leftText?: boolean;
    rightAxis?: boolean;
    rightTick?: boolean;
    rightText?: boolean;
    tooltip?: boolean;
    legend?: boolean;
    guideLine?: boolean;
}
interface CanvasLineChartArgs {
    id: string;
    series: DataType;
    axis: {
        bottom: BottomAxisInfo;
        left: AxisInfo;
        right?: AxisInfo;
    };
    width?: number;
    height?: number;
    renderOption?: RenderOption;
    pointSize?: number;
    font?: string;
    fontHeight?: number;
    canvasStyle?: {
        [key: string]: string;
    };
}
export { DataType, SeriesType, AxisInfo, BottomAxisInfo, RenderOption, CanvasLineChartArgs, };
