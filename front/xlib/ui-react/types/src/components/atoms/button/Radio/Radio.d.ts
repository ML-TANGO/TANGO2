/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
import i18n from 'react-i18next';
import { OptionType } from './types';
declare type Props = {
    options: OptionType[];
    selectedValue: string | number;
    name?: string;
    customStyle?: CSSProperties;
    theme?: ThemeType;
    testId?: string;
    tooltipValue?: Set<string | number>;
    isReadonly?: boolean;
    onTooltipRender?: (value: string | number) => React.ReactNode;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    t?: i18n.TFunction<'translation'>;
};
declare function Radio({ options, selectedValue, name, customStyle, theme, testId, tooltipValue, isReadonly, onTooltipRender, onChange, t, }: Props): JSX.Element;
declare namespace Radio {
    var defaultProps: {
        name: undefined;
        customStyle: undefined;
        theme: "jp-primary";
        testId: undefined;
        tooltipValue: undefined;
        isReadonly: boolean;
        onTooltipRender: undefined;
        onChange: undefined;
        t: undefined;
    };
}
export default Radio;
