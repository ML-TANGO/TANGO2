export interface LineChartParam {
    data?: any;
    eleId: string;
    width?: number;
    height?: number;
    isResponsive?: boolean;
    legend?: boolean;
    scaleType?: string;
    xTickFormat?: any;
    xAxisMaxTicks?: number;
    yAxisMaxTicks?: number;
    tooltip?: {
        align?: string;
    };
}
export interface UpdateOptionType {
    width: number;
    height: number;
    isResponsive: boolean;
    legend: any;
    xTickFormat: any;
    xAxisMaxTicks: any;
}
export interface LineChartSeriesType {
    align: string;
    x: string;
    y: string;
    color: string;
    label: string;
    domain: number[];
}
