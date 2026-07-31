import { CanvasLineChartArgs } from './types';
declare type Props = CanvasLineChartArgs;
declare function CanvasLineChart({ id, series, axis, width, height, pointSize, font, fontHeight, canvasStyle, renderOption, }: Props): JSX.Element;
declare namespace CanvasLineChart {
    var defaultProps: {
        width: number;
        height: number;
        pointSize: number;
        font: string;
        fontHeight: number;
        canvasStyle: undefined;
        renderOption: {
            bottomAxis: boolean;
            bottomTick: boolean;
            bottomText: boolean;
            leftAxis: boolean;
            leftTick: boolean;
            leftText: boolean;
            rightAxis: boolean;
            rightTick: boolean;
            rightText: boolean;
            tooltip: boolean;
            guideLine: boolean;
        };
    };
}
export default CanvasLineChart;
