/// <reference types="react" />
export interface IconDataType {
    name: string;
    icon: string;
}
export interface IconArgs {
    IconCompoList?: IconComponentType[];
    IconComponent?: (props: React.SVGProps<SVGSVGElement>) => JSX.Element;
    IconComponentProps?: React.SVGProps<SVGSVGElement>;
    name?: string;
    viewAllIcons?: boolean;
}
export interface IconComponentType {
    Component: (props: React.SVGProps<SVGSVGElement>) => JSX.Element;
    props?: React.SVGProps<SVGSVGElement>;
    name: string;
}
export declare const IconCompoList: {
    Component: (props: import("react").SVGProps<SVGSVGElement>) => JSX.Element;
    props: {
        width: number;
        height: number;
    };
    name: string;
}[];
