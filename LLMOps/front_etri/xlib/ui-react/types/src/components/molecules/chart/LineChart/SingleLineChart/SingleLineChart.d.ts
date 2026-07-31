import { SeriesType, DataType } from '../types';
declare type Props = {
    id: string;
    width: number;
    height: number;
    isResponsive: boolean;
    legend: boolean;
    series: Array<SeriesType>;
    data: Array<DataType>;
    xTickFormat: any;
};
declare function SingleLineChart({ id, width, height, isResponsive, legend, series, data, xTickFormat, }: Props): JSX.Element;
export default SingleLineChart;
