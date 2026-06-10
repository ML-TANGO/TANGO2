/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
import i18n from 'react-i18next';
declare type Props = {
    status?: string;
    size?: string;
    name?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    disableClearBtn?: boolean;
    disableLeftIcon?: boolean;
    disableRightIcon?: boolean;
    placeholder?: string;
    value?: string;
    leftIcon?: string;
    rightIcon?: string;
    closeIcon?: string;
    customStyle?: CSSProperties;
    leftIconStyle?: CSSProperties;
    rightIconStyle?: CSSProperties;
    closeIconStyle?: CSSProperties;
    options?: {
        [key: string]: string;
    };
    tabIndex?: number;
    autoFocus?: boolean;
    isLowercase?: boolean;
    theme?: ThemeType;
    testId?: string;
    readonly onClear?: (e?: HTMLInputElement) => void;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    readonly onBlur?: (e?: React.ChangeEvent<HTMLInputElement>) => void;
    readonly onKeyDown?: (e?: React.KeyboardEvent<HTMLInputElement>) => void;
    readonly t?: i18n.TFunction<'translation'>;
};
declare function InputText({ status, size, name, isDisabled, isReadOnly, disableClearBtn, disableLeftIcon, disableRightIcon, placeholder, value, leftIcon, rightIcon, closeIcon, customStyle, leftIconStyle, rightIconStyle, closeIconStyle, options, tabIndex, onChange, onClear, onBlur, onKeyDown, autoFocus, isLowercase, theme, testId, t, }: Props): JSX.Element;
declare namespace InputText {
    var defaultProps: {
        status: string;
        size: string;
        name: undefined;
        isDisabled: boolean;
        isReadOnly: boolean;
        disableClearBtn: boolean;
        disableLeftIcon: boolean;
        disableRightIcon: boolean;
        placeholder: undefined;
        value: undefined;
        leftIcon: string;
        rightIcon: undefined;
        closeIcon: string;
        customStyle: undefined;
        closeIconStyle: undefined;
        leftIconStyle: undefined;
        rightIconStyle: undefined;
        options: undefined;
        tabIndex: undefined;
        onClear: undefined;
        onChange: undefined;
        onKeyDown: undefined;
        onBlur: undefined;
        autoFocus: boolean;
        isLowercase: boolean;
        theme: "jp-primary";
        testId: undefined;
        t: undefined;
    };
}
export default InputText;
