/// <reference types="react" />
export interface PageTemplateArgs {
    theme?: ThemeType;
    headerRender?: (hideMenuBtn?: boolean, expandHandler?: () => void) => JSX.Element;
    sideNavRender?: () => JSX.Element;
    slidePanelRender: () => JSX.Element;
    footerRender?: () => JSX.Element;
    contentRef?: React.RefObject<HTMLDivElement>;
    children: any;
}
declare function PageTemplate({ headerRender, sideNavRender, slidePanelRender, footerRender, contentRef, children, theme, }: PageTemplateArgs): JSX.Element;
declare namespace PageTemplate {
    var defaultProps: {
        theme: "jp-primary";
        headerRender: undefined;
        sideNavRender: undefined;
        footerRender: undefined;
        contentRef: null;
    };
}
export default PageTemplate;
