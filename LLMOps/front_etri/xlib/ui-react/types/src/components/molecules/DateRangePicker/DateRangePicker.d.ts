/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
import { CustomStyleType } from './types';
declare type Props = {
    type?: string;
    status?: string;
    inputSize?: string;
    calendarSize?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    fromPlaceholder?: string;
    toPlaceholder?: string;
    from?: string;
    to?: string;
    maxDate?: string;
    minDate?: string;
    today?: string;
    submitLabel?: string;
    cancelLabel?: string;
    customStyle?: {
        primaryType?: CustomStyleType;
        splitType?: CustomStyleType;
        globalForm?: CSSProperties;
    };
    onErrorMessage?: (e: string) => void;
    onCellRender?: (d: any, propItem: {
        [key: string]: any;
    }) => React.ReactNode;
    onSubmit?: (from: string, to: string, e?: React.MouseEvent<HTMLButtonElement>) => void;
    onCalendarMount?: () => void;
    onCalendarChangeDetector?: (left: string, right: string) => void;
    scrollHandler?: () => void;
    t?: i18n.TFunction<'translation'>;
};
declare function DateRangePicker({ type, status, inputSize, calendarSize, fromPlaceholder, toPlaceholder, isDisabled, isReadOnly, from, to, maxDate, minDate, today, submitLabel, cancelLabel, customStyle, onErrorMessage, onCellRender, onSubmit, onCalendarMount, onCalendarChangeDetector, scrollHandler, t, }: Props): JSX.Element;
declare namespace DateRangePicker {
    var defaultProps: {
        type: string;
        status: string;
        inputSize: string;
        calendarSize: string;
        from: string;
        to: string;
        isDisabled: boolean;
        isReadOnly: boolean;
        fromPlaceholder: string;
        toPlaceholder: string;
        maxDate: string;
        minDate: string;
        today: string;
        submitLabel: string;
        cancelLabel: string;
        customStyle: undefined;
        onErrorMessage: undefined;
        onCellRender: undefined;
        onSubmit: undefined;
        onCalendarMount: undefined;
        onCalendarChangeDetector: undefined;
        scrollHandler: undefined;
        t: undefined;
    };
}
export default DateRangePicker;
