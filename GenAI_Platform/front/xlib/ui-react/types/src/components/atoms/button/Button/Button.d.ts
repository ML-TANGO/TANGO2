/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    type?: string;
    size?: string;
    theme?: ThemeType;
    children?: any;
    disabled?: boolean;
    icon?: string;
    iconAlign?: string;
    iconStyle?: CSSProperties;
    customStyle?: CSSProperties;
    testId?: string;
    title?: string;
    loading?: boolean;
    btnType?: 'button' | 'submit' | 'reset';
    readonly onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    readonly onMouseOver?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    readonly onMouseOut?: (e: React.MouseEvent<HTMLButtonElement>) => void;
};
declare function Button({ type, size, theme, children, disabled, icon, iconAlign, iconStyle, customStyle, testId, title, loading, btnType, onClick, onMouseOver, onMouseOut, }: Props): JSX.Element;
declare namespace Button {
    var defaultProps: {
        type: string;
        size: string;
        theme: "jp-primary";
        children: undefined;
        disabled: boolean;
        icon: undefined;
        iconAlign: string;
        iconStyle: undefined;
        btnType: string;
        customStyle: undefined;
        testId: undefined;
        title: undefined;
        loading: boolean;
        onClick: undefined;
        onMouseOver: undefined;
        onMouseOut: undefined;
    };
}
export default Button;
