/// <reference types="react" />
import { InputDateIconSizeType } from './types';
declare type Props = {
    status?: string;
    size?: string;
    value?: string;
    customSize?: InputDateIconSizeType;
    max?: number;
    min?: number;
    name?: string;
    disabled?: boolean;
    isReadOnly?: boolean;
    placeholder?: string;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
};
declare function InputDate({ status, size, placeholder, isReadOnly, disabled, value, max, min, name, customSize, onChange, }: Props): JSX.Element;
declare namespace InputDate {
    var defaultProps: {
        value: string;
        status: string;
        size: string;
        max: undefined;
        min: undefined;
        disabled: boolean;
        isReadOnly: boolean;
        placeholder: undefined;
        customSize: undefined;
        onChange: undefined;
        name: undefined;
    };
}
export default InputDate;
