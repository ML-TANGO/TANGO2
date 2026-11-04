import * as GlobalType from '@src/types';
import * as CanvasChartTypes from './CanvasChartTypes';
declare class CanvasChart {
    /**
     * HTML5 Canvas 설정
     */
    protected parentNode: HTMLElement | null;
    protected parentNodeId: string;
    protected canvasContainer: HTMLElement | null;
    protected canvasLayer: CanvasChartTypes.CanvasLayerType[];
    protected tooltip: HTMLElement | null;
    protected tooltipTemplate: string | null;
    protected legend: HTMLElement | null;
    protected events: Array<any>;
    protected width: number;
    protected height: number;
    protected mainChartIdx: number;
    protected animationChartIdx: number;
    protected defaultValue: GlobalType.ObjectType;
    constructor({ nodeId, width, height, canvasLayer, }: CanvasChartTypes.CanvasChartParam);
    /**
     * canvasLayer[canvasIdx]의 배경 수정
     */
    protected ctxFillRect(canvasIdx: number): void;
    protected ctxClear(): void;
    /**
     * mouse 커서의 좌표 계산
     * @param x - mouseover이벤트의 e.clientX
     * @param y - mouseover이벤트의 e.clientY
     * @returns - 마우스 좌표
     */
    protected mousePosition(x: number, y: number): {
        x: number;
        y: number;
    };
    /**
     * Canvas 크기보정
     */
    protected correctionCanvas(): void;
    /**
     * canvas observer 메서드
     * @param run canvas노드를 감지했을때 실행할 메서드
     * @param stop canvas노드가 사라졌을때 실행할 메서드
     */
    protected canvasObserver(run?: () => void, stop?: () => void): void;
    /**
     * event함수를 관리하는 events 배열
     * @param eventFunc
     */
    protected addEvents(eventFunc: Array<any>): void;
    /**
     * event remove
     */
    protected removeEvents(): void;
    protected appendCanvasNode(): void;
}
export default CanvasChart;
