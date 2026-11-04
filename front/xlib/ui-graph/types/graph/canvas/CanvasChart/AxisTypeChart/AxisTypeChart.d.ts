import CanvasChart from '../CanvasChart';
import * as AxisChartType from './AxisTypeChartTypes';
import { Vector } from '@src/types';
declare class AxisTypeChart extends CanvasChart {
    protected series: AxisChartType.SeriesDataType | null;
    protected axis: AxisChartType.AxisType | null;
    protected font: string;
    protected fontHeight: number;
    protected range: AxisChartType.AxisPositionType<number>;
    protected scale: number;
    protected startPoint: AxisChartType.AxisPositionType<Vector>;
    protected area: {
        start: Vector;
        end: Vector;
    };
    protected elementArea: AxisChartType.AxisPositionType<number>;
    protected middlePosition: number;
    protected renderOption: AxisChartType.RenderOption;
    protected createdNode: {
        legend: boolean;
        tooltip: boolean;
    };
    constructor({ nodeId, canvasLayer, width, height, font, fontHeight, }: AxisChartType.AxisTypeChartParam);
    /**
     * axis 최대, 최소값 설정
     */
    protected calcMax(): void;
    /**
     * 그래프 비율 계산
     */
    protected calcRelation(): void;
    /**
     * draw x축, y축
     */
    protected drawAxis(): void;
    /**
     * draw x축 tick, text
     */
    protected drawBottomTickAndText(): void;
    /**
     * draw left y축 tick, text
     */
    protected drawLeftTickAndText(): void;
    /**
     * draw right y축 tick, value
     */
    protected drawRightTickAndText(): void;
    /**
     * tooltip 생성
     */
    protected tooltipSetting(): void;
    /**
     * Draw legend
     */
    protected drawLegend(): void;
    /**
     * 현재 mouseover에 대한 x축의 영역에 대한 값 반환
     * @param dataArea {number} x축 영역
     * @returns number - x축 영역별 값
     */
    private innerInfoBottomAxis;
    /**
     * 현재 mouseover에 대한 x축의 영역에 대한 left축에 종속된 데이터 정보 반환
     * @param dataArea {number} - mouseover x축 영역
     * @returns leftInfo - left축에 대한 데이터의 정보 배열
     */
    private innerInfoLeftData;
    /**
     * 현재 mouseover에 대한 x축의 영역에 대한 right축에 종속된 데이터 정보 반환
     * @param dataArea {number} - mouseover x축 영역
     * @returns rightInfo - right축에 대한 데이터의 정보 배열
     */
    private innerInfoRightData;
    /**
     * draw tooltip
     * @param x {number} mouse x좌표
     * @param y {number} mouse y좌표
     * @param outputPosX {number} tooltip이 표시될 x좌표
     * @param outputPosY {number} tooltip이 표시될 y좌표
     */
    protected tooltipMaker(x: number, y: number, outputPosX: number, outputPosY: number): void;
    /**
     * 마우스 커서의 가이드라인 출력
     * @param x - 마우스 좌표 x
     * @param y - 마우스 좌표 y
     */
    protected drawGuidelines(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, x: number, y: number): void;
    protected mouseout(): () => void;
    /**
     * canvas 마우스 이벤트 등록
     */
    protected drawMouseOver(): (() => void) | null;
    /**
     * canvas reactive
     */
    protected canvasResize(run?: () => void): () => void;
}
export default AxisTypeChart;
