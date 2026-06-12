/// <reference types="react" />
declare type Props = {
    IconComponent?: (props: React.SVGProps<SVGSVGElement>) => JSX.Element;
    IconComponentProps?: React.SVGProps<SVGSVGElement>;
    name?: string;
};
declare function Icon({ IconComponent, IconComponentProps, name }: Props): JSX.Element;
declare namespace Icon {
    var defaultProps: {
        IconComponent: undefined;
        IconComponentProps: undefined;
        name: undefined;
    };
}
export default Icon;
