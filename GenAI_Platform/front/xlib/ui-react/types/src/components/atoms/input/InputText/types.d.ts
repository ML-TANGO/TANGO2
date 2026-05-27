/// <reference types="react" />
export interface InputStatusType {
    readonly DEFAULT: string;
    readonly ERROR: string;
}
export interface InputSizeType {
    readonly LARGE: string;
    readonly MEDIUM: string;
    readonly SMALL: string;
    readonly XSMALL: string;
}
export declare const InputStatus: InputStatusType;
export declare const InputSize: InputSizeType;
export interface InputTextArgs {
    status?: string;
    size?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    disableClearBtn?: boolean;
    disableLeftIcon?: boolean;
    disableRightIcon?: boolean;
    placeholder?: string;
    leftIcon?: string;
    rightIcon?: string;
    closeIcon?: string;
    customStyle: {
        [key: string]: string;
    };
    options: {
        [key: string]: string;
    };
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    readonly onClear?: (e: HTMLInputElement) => void;
    theme?: ThemeType;
}
