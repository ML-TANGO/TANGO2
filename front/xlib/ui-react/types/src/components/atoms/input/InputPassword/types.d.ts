/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
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
export interface InputPasswordArgs {
    status?: string;
    size?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    disableLeftIcon?: boolean;
    disableShowBtn?: boolean;
    placeholder?: string;
    leftIcon?: string;
    customStyle?: CSSProperties;
    options?: {
        [key: string]: string;
    };
    theme: ThemeType;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}
