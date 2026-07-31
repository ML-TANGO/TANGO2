export interface ChartTypes {
    SINGLE: string;
    MULTI: string;
}
export interface DataType {
    x: number;
    y1: number;
    y2: number;
}
export interface SeriesType {
    align: string;
    x: string;
    y: string;
    color: string;
    label: string;
    domain: number[];
}
export declare const chartTypes: ChartTypes;
export declare const data: DataType[];
export interface LineChartArgs {
    data: DataType[];
    type?: string;
    id?: string;
    width?: number;
    height?: number;
    isResponsive?: boolean;
    legend?: boolean;
    series?: SeriesType[];
    xTickFormat?: any;
}
