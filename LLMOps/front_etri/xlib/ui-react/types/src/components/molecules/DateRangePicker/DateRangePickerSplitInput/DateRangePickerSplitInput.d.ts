/// <reference types="react" />
import i18n from 'react-i18next';
import { CalendarType, CustomStyleType } from '../types';
declare type Props = {
    status: string;
    inputSize: string;
    placeholder: string;
    calendarType: CalendarType;
    value: string;
    isValidate: boolean;
    isDisabled: boolean;
    isReadOnly: boolean;
    customStyle?: CustomStyleType;
    onOpenCalendar: () => void;
    onInputChange: (calendarType: CalendarType, e: React.ChangeEvent<HTMLInputElement>) => void;
    t?: i18n.TFunction<'translation'>;
};
declare const DateRangePickerSplitInput: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLInputElement>>;
export default DateRangePickerSplitInput;
