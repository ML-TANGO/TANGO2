/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
import i18n from 'react-i18next';
declare type Props = {
    status?: string;
    size?: string;
    name?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    disableLeftIcon?: boolean;
    disableShowBtn?: boolean;
    placeholder?: string;
    value?: string;
    leftIcon?: string;
    customStyle?: CSSProperties;
    options?: {
        [key: string]: string;
    };
    tabIndex?: number;
    autoFocus?: boolean;
    testId?: string;
    theme?: ThemeType;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    readonly onKeyPress?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
    readonly t?: i18n.TFunction<'translation'>;
};
declare function InputPassword({ status, size, name, isDisabled, isReadOnly, disableLeftIcon, disableShowBtn, placeholder, value, leftIcon, customStyle, options, tabIndex, autoFocus, testId, onChange, onKeyPress, t, theme, }: Props): JSX.Element;
declare namespace InputPassword {
    var defaultProps: {
        status: string;
        size: string;
        name: undefined;
        isDisabled: boolean;
        isReadOnly: boolean;
        disableLeftIcon: boolean;
        disableShowBtn: boolean;
        placeholder: undefined;
        value: undefined;
        leftIcon: string;
        customStyle: undefined;
        options: undefined;
        tabIndex: undefined;
        autoFocus: boolean;
        testId: undefined;
        onChange: undefined;
        onKeyPress: undefined;
        t: undefined;
        theme: "jp-primary";
    };
}
export default InputPassword;
