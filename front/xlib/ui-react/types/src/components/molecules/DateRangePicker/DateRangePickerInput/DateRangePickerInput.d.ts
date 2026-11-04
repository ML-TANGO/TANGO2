/// <reference types="react" />
import i18n from 'react-i18next';
import { CalendarType, CustomStyleType } from '../types';
declare type Props = {
    status: string;
    inputSize: string;
    fromPlaceholder: string;
    toPlaceholder: string;
    fromDate: string;
    toDate: string;
    isReadonly: boolean;
    isDisable: boolean;
    fromValidation: boolean;
    toValidation: boolean;
    isOpenCalendar: boolean;
    customStyle?: CustomStyleType;
    onOpenCalendar: () => void;
    onInputChange: (calendarType: CalendarType, e: React.ChangeEvent<HTMLInputElement>) => void;
    t?: i18n.TFunction<'translation'>;
};
declare const DateRangePickerInput: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLDivElement>>;
export default DateRangePickerInput;
