/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    checked?: boolean;
    disabled?: boolean;
    label?: string;
    theme?: ThemeType;
    customLabelStyle?: {
        [key: string]: string;
    };
    customStyle?: CSSProperties;
    name?: string;
    value?: number;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
};
declare function Checkbox({ label, checked, disabled, customLabelStyle, customStyle, onChange, theme, name, value, }: Props): JSX.Element;
declare namespace Checkbox {
    var defaultProps: {
        checked: boolean;
        disabled: boolean;
        label: undefined;
        onChange: undefined;
        theme: "jp-primary";
        customLabelStyle: undefined;
        customStyle: undefined;
        name: undefined;
        value: undefined;
    };
}
export default Checkbox;
