import { LineChartArgs } from './types';
declare type Props = LineChartArgs;
declare function LineChart({ id, type, width, height, isResponsive, legend, series, data, xTickFormat, }: Props): JSX.Element;
declare namespace LineChart {
    var defaultProps: {
        id: string;
        type: string;
        width: number;
        height: number;
        isResponsive: boolean;
        legend: boolean;
        series: undefined;
    };
}
export default LineChart;
