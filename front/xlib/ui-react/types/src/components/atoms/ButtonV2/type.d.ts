import { ReactNode } from 'react';
export declare const BUTTON_TYPES: readonly ["solid", "clear", "outline"];
export declare const BUTTON_COLORS: readonly ["blue", "white", "skyblue", "red", "lightRed", "gray"];
export declare const BUTTON_SIZES: readonly ["s", "m", "l", "xl"];
export declare const BUTTON_ICON_POSITIONS: readonly ["left", "right"];
export declare type TButtonType = typeof BUTTON_TYPES[number];
export declare type TButtonColor = typeof BUTTON_COLORS[number];
export declare type TButtonSize = typeof BUTTON_SIZES[number];
export declare type TButtonIconPosition = typeof BUTTON_ICON_POSITIONS[number];
export interface ButtonV2Props {
    children?: ReactNode;
    label?: string;
    type?: TButtonType;
    colorType?: TButtonColor;
    size?: TButtonSize;
    icon?: string;
    iconPosition?: TButtonIconPosition;
    isLoading?: boolean;
    disabled?: boolean;
    boxShadow?: boolean;
    onClick?: () => void;
}
