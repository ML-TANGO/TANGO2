import { SeriesType, DataType } from '../types';
declare type Props = {
    id: string;
    width: number;
    height: number;
    isResponsive: boolean;
    legend: boolean;
    series: SeriesType[];
    data: DataType[];
    xTickFormat: any;
};
declare function MultiLineChart({ id, width, height, isResponsive, legend, series, data, xTickFormat, }: Props): JSX.Element;
export default MultiLineChart;
