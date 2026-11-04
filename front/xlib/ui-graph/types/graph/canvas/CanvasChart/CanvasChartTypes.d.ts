import { ObjectType } from '@src/types';
interface CanvasLayer {
    type: 'main' | 'static' | 'animation';
    id: string;
    canvasStyle: ObjectType;
}
interface CanvasLayerType extends CanvasLayer {
    canvas: HTMLCanvasElement;
    ctx: CanvasRenderingContext2D | null;
}
interface CanvasChartParam {
    nodeId: string;
    width: number;
    height: number;
    canvasLayer: CanvasLayer[];
}
export { CanvasChartParam, CanvasLayerType, CanvasLayer };
