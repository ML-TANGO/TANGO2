export interface LabelType {
    text: any | any[];
    color?: string;
    style?: string;
}
export interface PieChartDataTypes {
    title?: any;
    titlePosition?: number;
    value: number;
    color: string;
}
export interface ChartBolderType {
    designatedBolder?: 'large' | 'medium' | 'small' | 'x-small';
    custom?: number;
}
export interface PieChartArgs {
    data: PieChartDataTypes[];
    chartSize?: number;
    chartFillColor?: string;
    chartBolder?: ChartBolderType;
    centerText?: LabelType;
    totalValue?: number;
}
