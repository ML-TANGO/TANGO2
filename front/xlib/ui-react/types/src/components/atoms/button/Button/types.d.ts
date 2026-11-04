/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
export interface ButtonTypeTypes {
    readonly PRIMARY: string;
    readonly PRIMARY_REVERSE: string;
    readonly PRIMARY_LIGHT: string;
    readonly RED: string;
    readonly RED_REVERSE: string;
    readonly RED_LIGHT: string;
    readonly SECONDARY: string;
    readonly GRAY: string;
    readonly NONE_BORDER: string;
    readonly TEXT_UNDERLINE: string;
}
export interface ButtonSizeType {
    readonly LARGE: string;
    readonly MEDIUM: string;
    readonly SMALL: string;
    readonly X_SMALL: string;
}
export interface ButtonIconAlignType {
    readonly LEFT: string;
    readonly RIGHT: string;
}
export declare const ButtonType: ButtonTypeTypes;
export declare const ButtonSize: ButtonSizeType;
export declare const ButtonIconAlign: ButtonIconAlignType;
export interface ButtonArgs {
    type?: string;
    size?: string;
    children?: string;
    icon?: string;
    theme?: ThemeType;
    iconAlign?: string;
    iconStyle?: {
        [key: string]: string;
    };
    disabled?: boolean;
    customStyle?: CSSProperties;
    testId?: string;
    loading?: boolean;
    readonly onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    readonly onMouseOver?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    readonly onMouseOut?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}
