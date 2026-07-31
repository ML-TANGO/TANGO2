/// <reference types="react" />
export interface InputDateStatusType {
    DEFAULT: string;
    ERROR: string;
}
export interface InputDateSizeType {
    LARGE: string;
    MEDIUM: string;
    SMALL: string;
    XSMALL: string;
}
export interface InputDateIconTypes {
    UP_ICON: string;
    DOWN_ICON: string;
}
export interface InputDateIconSizeType {
    width?: string;
    height?: string;
}
export declare const InputDateStatus: InputDateStatusType;
export declare const InputDateSize: InputDateSizeType;
export interface InputDateArgs {
    status?: string;
    size?: string;
    max?: number;
    min?: number;
    value?: string;
    name?: string;
    disabled?: boolean;
    isReadOnly?: boolean;
    placeholder?: string;
    customSize?: InputDateIconSizeType;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}
