import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    title?: string;
    contents?: string;
    type?: string;
    isTail?: boolean;
    customStyle?: CSSProperties;
    contentsAlign?: {
        vertical?: 'bottom' | 'top';
        horizontal?: 'left' | 'right' | 'center';
    };
    tooltipHandler: (flag?: boolean) => void;
};
declare function Balloon({ title, contents, type, isTail, customStyle, contentsAlign, tooltipHandler, }: Props): JSX.Element;
declare namespace Balloon {
    var defaultProps: {
        title: undefined;
        contents: undefined;
        type: "light";
        isTail: boolean;
        customStyle: undefined;
        contentsAlign: {
            vertical: "bottom";
            horizontal: "left";
        };
    };
}
export default Balloon;
