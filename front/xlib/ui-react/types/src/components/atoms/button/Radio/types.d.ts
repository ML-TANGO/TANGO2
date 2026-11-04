/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
interface OptionType {
    label: string;
    value: string | number;
    disabled: boolean;
    icon?: string;
    labelStyle?: CSSProperties;
    customStyle?: CSSProperties;
}
interface RadioArgs {
    options: OptionType[];
    name?: string;
    customStyle?: CSSProperties;
    isReadonly?: boolean;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}
declare const mockData: OptionType[];
export { RadioArgs, OptionType, mockData };
