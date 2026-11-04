import { TSpinnerColor } from './types';
declare type Props = {
    size?: 'xs' | 'sm' | 'md' | 'lg';
    color?: TSpinnerColor;
};
declare function Spinner({ size, color }: Props): JSX.Element;
declare namespace Spinner {
    var defaultProps: {
        size: string;
        color: string;
    };
}
export default Spinner;
