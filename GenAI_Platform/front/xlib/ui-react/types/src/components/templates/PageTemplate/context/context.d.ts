/// <reference types="react" />
declare type Props = {
    children: React.ReactNode;
};
declare const PageTemplateContext: import("react").Context<{}>;
declare const PageTemplateContextProvider: ({ children }: Props) => JSX.Element;
export { PageTemplateContextProvider, PageTemplateContext };
