export declare const MODAL_OPEN = "modal/OPEN";
export declare const MODAL_CLOSE = "modal/CLOSE";
export declare const MODAL_FULL_SIZE = "modal/FULL_SIZE";
export declare const modalOpen: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const modalClose: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const modalFullSize: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare type ModalAction = ReturnType<typeof modalOpen> | ReturnType<typeof modalClose> | ReturnType<typeof modalFullSize>;
export interface ModalState {
    isOpen: boolean;
    isFullSize: boolean;
    headerRender?: any;
    contentRender?: any;
    footerRender?: any;
}
export declare const initModalState: ModalState;
declare const _default: import("redux-actions").ReduxCompatibleReducer<ModalState, import("redux-actions").Action<any>>;
export default _default;
