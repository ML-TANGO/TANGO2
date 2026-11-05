import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    isBox?: boolean;
    customStyle?: CSSProperties;
    text?: string;
    theme?: ThemeType;
    t?: i18n.TFunction<'translation'>;
};
declare function Emptybox({ isBox, customStyle, theme, text, t }: Props): JSX.Element;
declare namespace Emptybox {
    var defaultProps: {
        isBox: boolean;
        customStyle: undefined;
        text: string;
        theme: "jp-primary";
        t: undefined;
    };
}
export default Emptybox;
