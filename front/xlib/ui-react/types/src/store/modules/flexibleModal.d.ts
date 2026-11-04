import { ModalTemplateArgs } from '@src/components/molecules/FlexibleModal/types';
export declare const FMODAL_OPEN = "fmodal/OPEN";
export declare const FMODAL_CLOSE = "fmodal/CLOSE";
export declare const FMODAL_MINIMIZE = "fmodal/MINIMIZE";
export declare const FMODAL_MAXIMIZE = "fmodal/MAXIMIZE";
export declare const FMODAL_CLOSE_ALL = "fmodal/CLOSE_ALL";
export declare const FMODAL_FULLSCREEN = "fmodal/FULLSCREEN";
export declare const fmodalOpen: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const fmodalClose: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const fmodalMinimize: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const fmodalMaximize: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const fmodalCloseAll: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare const fmodalFullscreen: import("redux-actions").ActionFunctionAny<import("redux-actions").Action<any>>;
export declare type FModalAction = ReturnType<typeof fmodalOpen> | ReturnType<typeof fmodalClose> | ReturnType<typeof fmodalMinimize> | ReturnType<typeof fmodalMaximize> | ReturnType<typeof fmodalCloseAll> | ReturnType<typeof fmodalFullscreen>;
export interface FModalState {
    modalList: ModalTemplateArgs[];
}
export declare const initModalState: FModalState;
declare const _default: import("redux-actions").ReduxCompatibleReducer<FModalState, import("redux-actions").Action<any>>;
export default _default;
