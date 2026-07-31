/// <reference types="react" />
import i18n from 'react-i18next';
import { CalendarType } from '../../types';
declare type Props = {
    calendarType: CalendarType;
    today: string;
    selectedFromDate: string;
    selectedToDate: string;
    fromCalendarDate: string;
    toCalendarDate: string;
    minDate: string;
    maxDate: string;
    calendarSize: string;
    calendarTable: string[][];
    readonly onChangeCalendar: (calendarType: CalendarType, movePos: 'BACK' | 'FRONT') => void;
    readonly onSelectDate: (date: string, calendarType: CalendarType) => void;
    readonly onCellRender?: (d: any, propItem: {
        [key: string]: any;
    }) => React.ReactNode;
    readonly t?: i18n.TFunction<'translation'>;
};
declare function Calendar({ calendarType, today, fromCalendarDate, toCalendarDate, selectedFromDate, selectedToDate, minDate, maxDate, calendarSize, calendarTable, onSelectDate, onChangeCalendar, onCellRender, t, }: Props): JSX.Element;
declare namespace Calendar {
    var defaultProps: {
        onCellRender: undefined;
        t: undefined;
    };
}
export default Calendar;
