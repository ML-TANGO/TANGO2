import { ReactNode } from 'react';
declare const POPUP_TYPES: readonly ["main", "delete", "sub"];
export declare type TPopupType = typeof POPUP_TYPES[number];
export interface PopupProps {
    type?: TPopupType;
    frontTitle?: ReactNode;
    isAnimation?: boolean;
    isLoading?: boolean;
    popupTitle?: string;
    popupContents?: string | ReactNode;
    cancelBtnLabel?: string;
    submitBtnLabel?: string;
    handleCancel: () => void;
    handleSubmit: () => void;
}
export {};
