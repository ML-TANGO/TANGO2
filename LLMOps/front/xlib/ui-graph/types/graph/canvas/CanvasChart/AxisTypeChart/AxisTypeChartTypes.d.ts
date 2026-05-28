import { CanvasChartParam } from '../CanvasChartTypes';
interface AxisPositionType<T> {
    left: T;
    bottom: T;
    right: T;
}
interface Series {
    name: string;
    series: number[];
}
interface SeriesType extends Series {
    color: string;
    lineWidth: number;
}
interface SeriesParamType extends Series {
    color?: string;
    lineWidth?: number;
}
interface AxisType {
    left: AxisInfo;
    right: AxisInfo;
    bottom: BottomAxisInfo;
}
interface AxisParamType {
    left?: AxisParamInfo;
    right?: AxisParamInfo;
    bottom: BottomAxisParamInfo;
}
interface SeriesDataType {
    left: SeriesType[];
    right: SeriesType[];
}
interface DataParamType {
    left: SeriesParamType[];
    bottom?: SeriesParamType[];
    right?: SeriesParamType[];
}
interface AxisInfo {
    name: string;
    unitsPerTick: number;
    max: number;
    min: number;
    padding: number;
    tickSize: number;
    tickColor: string;
    lineWidth: number;
    color: string;
}
interface BottomAxisInfo extends AxisInfo {
    data: number[] | string[];
}
interface AxisParamInfo {
    name?: string;
    unitsPerTick?: number;
    max?: number;
    min?: number;
    padding?: number;
    tickSize?: number;
    tickColor?: string;
    lineWidth?: number;
    color?: string;
}
interface BottomAxisParamInfo extends AxisParamInfo {
    data?: number[] | string[];
}
interface AxisTypeChartParam extends CanvasChartParam {
    point?: number;
    font?: string;
    fontHeight?: number;
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
export { AxisPositionType, Series, SeriesType, SeriesParamType, AxisType, AxisParamType, SeriesDataType, DataParamType, AxisInfo, AxisParamInfo, BottomAxisInfo, BottomAxisParamInfo, RenderOption, AxisTypeChartParam, };
