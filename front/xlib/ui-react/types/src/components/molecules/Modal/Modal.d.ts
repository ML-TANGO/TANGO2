import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    HeaderRender?: () => JSX.Element;
    ContentRender?: () => JSX.Element;
    FooterRender?: () => JSX.Element;
    headerProps?: any;
    footerProps?: any;
    contentProps?: any;
    windowStyle?: CSSProperties;
    headerStyle?: CSSProperties;
    contentStyle?: CSSProperties;
    footerStyle?: CSSProperties;
    topAnimation?: string;
    theme?: ThemeType;
};
declare function Modal({ HeaderRender, ContentRender, FooterRender, headerProps, footerProps, contentProps, windowStyle, headerStyle, contentStyle, footerStyle, topAnimation, theme, }: Props): JSX.Element;
declare namespace Modal {
    var defaultProps: {
        HeaderRender: undefined;
        ContentRender: undefined;
        FooterRender: undefined;
        headerProps: undefined;
        footerProps: undefined;
        contentProps: undefined;
        windowStyle: undefined;
        headerStyle: undefined;
        contentStyle: undefined;
        footerStyle: undefined;
        topAnimation: string;
        theme: "jp-primary";
    };
}
export default Modal;
