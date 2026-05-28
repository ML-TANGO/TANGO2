import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    type?: 'primary' | 'circle';
    size?: 'small' | 'medium' | 'large';
    customStyle?: CSSProperties;
};
declare function Loading({ type, size, customStyle }: Props): JSX.Element;
declare namespace Loading {
    var defaultProps: {
        type: string;
        size: string;
        customStyle: undefined;
    };
}
export default Loading;
