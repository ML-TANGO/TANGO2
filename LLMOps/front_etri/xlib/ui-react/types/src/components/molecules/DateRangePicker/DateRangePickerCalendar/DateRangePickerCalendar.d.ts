/// <reference types="react" />
import i18n from 'react-i18next';
import { CalendarType } from '../types';
declare type Props = {
    today: string;
    fromCalendarDate: string;
    toCalendarDate: string;
    selectedFromDate: string;
    selectedToDate: string;
    minDate: string;
    maxDate: string;
    calendarSize: string;
    fromValidation: boolean;
    toValidation: boolean;
    submitLabel: string;
    cancelLabel: string;
    fromCalendarTable: string[][];
    toCalendarTable: string[][];
    onSubmit: (e: React.MouseEvent<HTMLButtonElement>) => void;
    onCancel: () => void;
    onChangeCalendar: (calendarType: CalendarType, movePos: 'BACK' | 'FRONT') => void;
    onSelectDate: (date: string, calendarType: CalendarType) => void;
    onCellRender?: (d: any, propItem: {
        [key: string]: any;
    }) => React.ReactNode;
    onCalendarMount?: () => void;
    t?: i18n.TFunction<'translation'>;
};
declare const DateRangePickerCalendar: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLDivElement>>;
export default DateRangePickerCalendar;
