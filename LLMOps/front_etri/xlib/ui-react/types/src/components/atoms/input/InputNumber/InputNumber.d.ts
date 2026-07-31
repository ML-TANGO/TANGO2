/// <reference types="react" />
import i18n from 'react-i18next';
import { InputNumberDataType, InputNumberIconSizeType } from './types';
declare type Props = {
    status?: string;
    size?: string;
    value?: number;
    max?: number;
    min?: number;
    step?: number;
    name?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    placeholder?: string;
    upIcon?: string;
    downIcon?: string;
    customSize?: InputNumberIconSizeType;
    onChange?: (data: InputNumberDataType, e?: React.ChangeEvent<HTMLInputElement>) => void;
    onBlur?: (e?: React.ChangeEvent<HTMLInputElement>) => void;
    t?: i18n.TFunction<'translation'>;
    theme?: ThemeType;
    disableIcon?: boolean;
    bottomTextExist?: boolean;
    error?: string;
    info?: string;
    valueAlign?: string;
};
declare function InputNumber({ status, size, placeholder, isReadOnly, isDisabled, value, max, min, name, step, upIcon, downIcon, customSize, theme, disableIcon, bottomTextExist, error, info, valueAlign, onChange, onBlur, t, }: Props): JSX.Element;
declare namespace InputNumber {
    var defaultProps: {
        status: string;
        size: string;
        value: undefined;
        max: undefined;
        min: undefined;
        name: undefined;
        step: number;
        isDisabled: boolean;
        isReadOnly: boolean;
        placeholder: string;
        upIcon: string;
        downIcon: string;
        customSize: undefined;
        onChange: undefined;
        onBlur: undefined;
        t: undefined;
        theme: "jp-primary";
        disableIcon: boolean;
        bottomTextExist: boolean;
        error: undefined;
        info: undefined;
        valueAlign: string;
    };
}
export default InputNumber;
