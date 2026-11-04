import AxisTypeChart from '../AxisTypeChart';
import * as AxisChartType from '../AxisTypeChartTypes';
import * as LineChartType from './LineChartTypes';
declare class LineChart extends AxisTypeChart {
    private pointRadius;
    constructor({ nodeId, width, height, point, font, fontHeight, canvasStyle, }: LineChartType.LineChartParam);
    /**
     * Left축에 종속된 데이터(series) draw
     */
    private drawLeftLine;
    /**
     * right축에 종속된 데이터(series) draw
     */
    private drawRightLine;
    private draw;
    dataInitialize({ series, axis }: LineChartType.InitializeDataParam): void;
    render(renderOption?: AxisChartType.RenderOption): (() => void) | null;
}
export default LineChart;
