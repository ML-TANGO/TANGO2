import { ObjectType } from '@src/types';
import { DataParamType, AxisParamType } from '../AxisTypeChartTypes';
interface LineChartParam {
    nodeId: string;
    point?: number;
    font?: string;
    fontHeight: number;
    width?: number;
    height?: number;
    canvasStyle?: ObjectType;
}
interface InitializeDataParam {
    series: DataParamType;
    axis: AxisParamType;
}
export { LineChartParam, InitializeDataParam };
