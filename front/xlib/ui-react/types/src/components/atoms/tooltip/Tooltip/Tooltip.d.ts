/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    children?: React.ReactNode;
    customStyle?: CSSProperties;
    icon?: string;
    iconAlign?: 'left' | 'right';
    label?: string;
    title?: string;
    contents?: string;
    contentsAlign?: {
        vertical?: 'bottom' | 'top';
        horizontal?: 'left' | 'right' | 'center';
    };
    globalCustomStyle?: CSSProperties;
    iconCustomStyle?: CSSProperties;
    labelCustomStyle?: CSSProperties;
    contentsCustomStyle?: CSSProperties;
    type?: 'light' | 'dark';
    isTail?: boolean;
};
declare function Tooltip({ children, customStyle, icon, iconAlign, label, title, contents, contentsAlign, globalCustomStyle, iconCustomStyle, labelCustomStyle, contentsCustomStyle, type, isTail, }: Props): JSX.Element;
declare namespace Tooltip {
    var defaultProps: {
        children: undefined;
        customStyle: undefined;
        icon: string;
        iconAlign: "left";
        label: undefined;
        title: undefined;
        contents: undefined;
        contentsAlign: {
            vertical: "bottom";
            horizontal: "left";
        };
        globalCustomStyle: undefined;
        iconCustomStyle: undefined;
        labelCustomStyle: undefined;
        contentsCustomStyle: undefined;
        type: "light";
        isTail: boolean;
    };
}
export default Tooltip;
