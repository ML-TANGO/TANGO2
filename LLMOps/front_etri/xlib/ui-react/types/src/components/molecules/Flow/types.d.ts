export interface DataType {
    broadcastingStatus?: number;
    clientName?: string;
    metrics?: string;
    testStatus?: number;
    broadcastingSuccess?: number;
}
export interface MetricsDataType {
    key?: string;
    value?: string | number;
    change_direction?: string;
    change_amount?: string;
}
export interface GlobalModelDataType {
    metric?: string;
    seedModel?: number;
    resultModel?: number;
    change_direction?: string;
}
export interface FlowData {
    broadcastingStageStatus?: number;
    trainingStageStatus?: number;
    aggregationStatus?: number;
    metrics?: MetricsDataType[] | Array<any>;
    data?: DataType[] | Array<any>;
    globalModelData?: GlobalModelDataType[] | Array<any>;
    stageFailReason?: string;
}
export interface NodeDataType {
    type?: string;
    clientName?: string;
    dotPosition?: string;
    count?: number;
    learningResultValue?: number;
    learningStatus?: string;
}
export interface PositionData {
    x: number;
    y: number;
}
export interface NodeData {
    data?: NodeDataType;
    id?: string;
    position?: PositionData;
    sourcePosition?: string;
    type?: string;
}
export interface NodeDataValue {
    broadcastingStatus?: number;
    clientName?: string;
    metrics?: string;
    testStatus?: number;
    trainingStatus?: number;
}
