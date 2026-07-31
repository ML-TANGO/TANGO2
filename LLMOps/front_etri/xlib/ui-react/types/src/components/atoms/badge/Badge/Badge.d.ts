/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    label?: string;
    type?: string;
    title?: string;
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
    radius?: 'default' | 'small';
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
    customStyle?: CSSProperties;
};
declare function Badge({ label, type, title, size, radius, leftIcon, rightIcon, customStyle, }: Props): JSX.Element;
declare namespace Badge {
    var defaultProps: {
        label: undefined;
        type: undefined;
        title: undefined;
        radius: string;
        size: string;
        leftIcon: undefined;
        rightIcon: undefined;
        customStyle: undefined;
    };
}
export default Badge;
