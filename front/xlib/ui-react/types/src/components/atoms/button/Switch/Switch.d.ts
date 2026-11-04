/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    size?: string;
    checked: boolean;
    disabled?: boolean;
    label?: string;
    message?: string;
    customStyle?: CSSProperties;
    name?: string;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    labelAlign?: string;
};
declare function Switch({ size, checked, disabled, label, message, customStyle, name, onChange, labelAlign, }: Props): JSX.Element;
declare namespace Switch {
    var defaultProps: {
        size: string;
        disabled: boolean | undefined;
        label: undefined;
        message: undefined;
        customStyle: undefined;
        name: string;
        onChange: undefined;
        labelAlign: string;
    };
}
export default Switch;
