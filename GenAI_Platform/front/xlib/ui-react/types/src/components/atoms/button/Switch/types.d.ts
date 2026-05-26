/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
export interface SwitchSizeType {
    readonly X_LARGE: string;
    readonly LARGE: string;
    readonly MEDIUM: string;
    readonly SMALL: string;
}
export declare const SwitchSize: SwitchSizeType;
export interface SwitchArgs {
    size?: string;
    disabled?: boolean;
    label?: string;
    customStyle?: CSSProperties;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    labelAlign?: string;
}
export declare const initialLabelAlign: {
    LEFT: string;
    RIGHT: string;
};
export declare const SwitchInit: SwitchArgs;
