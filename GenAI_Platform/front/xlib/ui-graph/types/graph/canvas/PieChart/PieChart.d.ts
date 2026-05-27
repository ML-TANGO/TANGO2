import { PieChartParam } from './PieChartTypes';
declare class PieChart {
    private canvas;
    private ctx;
    private data?;
    private expressionData;
    private eachDataArea;
    private canvasSize;
    private chartSize;
    private chartPosition;
    private chartFillColor;
    private chartBolder?;
    private centerText?;
    private totalValue?;
    private radius;
    private degree;
    private circumference;
    private centerArcDegree;
    /**
     * craete PieChart
     * @param {string} eleId
     * @param {number | undefined} chartSize
     * @param {{
     *  title?: {
     *    text: string,
     *    color?: string,
     *    style?: string,
     *  },
     *  color: string,
     *  style: string,
     * }[]} data
     * @param {string | undefined} chartFillColor
     * @param {{
     *  designationBolder?: 'large' | 'medium' | 'small' | 'x-small',
     *  custom?: number,
     * }} chartBolder
     * @param {{
     *  text? {
     *    text: any | any[],
     *    color?: string,
     *    style?: string,
     *  }
     * }} centerText
     * @param {number | undefined} totalValue
     */
    constructor(params: PieChartParam);
    private correction;
    private calcData;
    private centerMake;
    private drawChart;
    private degreeToRadians;
    private titleDraw;
    private centerTextDraw;
    draw(): void;
}
export default PieChart;
