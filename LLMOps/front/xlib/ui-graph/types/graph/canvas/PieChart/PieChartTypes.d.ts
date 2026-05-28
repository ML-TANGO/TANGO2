export interface PieChartParam {
    canvas: HTMLCanvasElement;
    data: PieChartDataTypes[];
    chartSize?: number;
    chartFillColor?: string;
    chartBolder?: ChartBolderType;
    centerText?: LabelType;
    totalValue?: number;
}
export interface ChartBolderType {
    designatedBolder?: 'large' | 'medium' | 'small' | 'x-small';
    custom?: number;
}
export interface SizeType {
    width: number;
    height: number;
}
export interface LabelType {
    text: any | any[];
    color?: string;
    style?: string;
}
export interface PieChartDataTypes {
    title?: LabelType;
    value: number;
    color: string;
    titlePosition?: number;
}
export interface PieChartElement extends PieChartDataTypes {
    angleValue: number;
}
export interface EachDataAreaType {
    title?: LabelType;
    titlePosition?: number;
    startEndDegree: number;
}
export declare const chartBolders: {
    LARGE: string;
    MEDIUM: string;
    SMALL: string;
    XSMALL: string;
};
export declare const pieChartPrimaryStyle: {
    CHART_SIZE: number;
    CHART_COLOR: string;
    LABEL_COLOR: string;
    LABEL_STYLE: string;
};
