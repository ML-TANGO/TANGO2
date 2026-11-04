/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
import { RunningType, PendingType, DoneType, ErrorType, UnknownType, InProgressType } from './types';
declare type Props = {
    text?: string;
    status?: RunningType | PendingType | DoneType | ErrorType | UnknownType | InProgressType;
    size?: 'x-small' | 'small' | 'medium' | 'large';
    type?: 'help' | 'default';
    theme?: ThemeType;
    customStyle?: CSSProperties;
    isTooltip?: boolean;
    tooltipData?: {
        title?: string;
        description?: string;
    };
    isProgressStatus?: boolean;
    rightIcon?: string;
    leftIcon?: string;
    iconStyle?: CSSProperties;
    leftIconStyle?: CSSProperties;
    iconOnMouseOver?: () => void;
    iconOnMouseLeave?: () => void;
    tooltipComponent?: () => React.ReactNode;
    t?: i18n.TFunction<'translation'>;
};
declare function StatusCard({ text, status, size, type, theme, customStyle, isTooltip, tooltipData, isProgressStatus, rightIcon, leftIcon, leftIconStyle, iconStyle, iconOnMouseOver, iconOnMouseLeave, tooltipComponent, t, }: Props): JSX.Element;
declare namespace StatusCard {
    var defaultProps: {
        status: string;
        text: string;
        size: string;
        type: string;
        theme: "jp-primary";
        customStyle: undefined;
        tooltipComponent: undefined;
        tooltipData: undefined;
        isProgressStatus: boolean;
        rightIcon: undefined;
        leftIcon: undefined;
        iconStyle: undefined;
        leftIconStyle: undefined;
        iconOnMouseOver: undefined;
        iconOnMouseLeave: undefined;
        isTooltip: boolean;
        t: undefined;
    };
}
export default StatusCard;
