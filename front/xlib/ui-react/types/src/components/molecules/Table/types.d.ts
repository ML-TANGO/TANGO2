export interface ColumnElements {
    name: string;
    selector?: string;
    sortable?: boolean;
    cell?: () => any;
}
export interface ColumnsType {
    columns: ColumnElements[];
}
export interface TableStyle {
    bodyStyle?: {
        fontColor?: string;
        backgroundColor?: string;
        visibleLine?: boolean;
        visibleCellLine?: boolean;
        scrollbarColor?: 'light' | 'dark';
    };
    headerStyle?: {
        fontColor?: string;
        backgroundColor?: string;
    };
}
export interface TableBodyArgs extends ColumnsType, TableStyle {
    data: Array<any>;
    isCheck?: boolean;
    checked: any;
    isPageNation?: boolean;
    loading?: boolean;
    checkHandler: (idx: number) => void;
}
export interface TableHeaderArgs extends ColumnsType, TableStyle {
    isCheck?: boolean;
    isAllChecked?: boolean;
    InputSortIcon?: () => JSX.Element;
    readonly sortHandler?: (selector: string) => void;
    readonly checkHandler: (idx: number) => void;
}
export interface PagingArgs {
    pagingBtnAlign?: 'left' | 'center' | 'right';
    PagingBtn?: {
        MoveFirst?: () => JSX.Element;
        MoveLast?: () => JSX.Element;
        MovePrev: () => JSX.Element;
        MoveNext: () => JSX.Element;
    };
}
export interface PagingHookArgs extends PagingArgs {
    dataSize: number;
    rowSize?: number;
}
export interface PaginationArgs extends PagingArgs {
    loc: number;
    pageHandler: (action: string) => void;
    moveEdgePage: (action: string) => void;
}
export interface TableArgs extends ColumnsType, PagingArgs, TableStyle {
    data?: Array<any>;
    isCheck?: boolean;
    isPageNation?: boolean;
    pageRowCnt?: number;
    loading?: boolean;
    InputSortIcon?: () => JSX.Element;
    getCheckedIndex?: (prev: Array<any>) => Array<any>;
}
export declare const pageBtnAlign: {
    LEFT: string;
    CENTER: string;
    RIGHT: string;
};
