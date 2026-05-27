import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import Button from '../../../atoms/button/Button/Button.js';
import classNames from '../../../../../modules/classnames/bind.js';
import { forwardRef, useEffect } from 'react';
import { initCalendarSize } from '../types.js';
import Calendar from './Calendar/Calendar.js';
import style from './DateRangePickerCalendar.module.scss.js';

var cx = classNames.bind(style);
var DateRangePickerCalendar = forwardRef(function (_a, ref) {
    var today = _a.today, fromCalendarDate = _a.fromCalendarDate, toCalendarDate = _a.toCalendarDate, selectedFromDate = _a.selectedFromDate, selectedToDate = _a.selectedToDate, minDate = _a.minDate, maxDate = _a.maxDate, calendarSize = _a.calendarSize, fromValidation = _a.fromValidation, toValidation = _a.toValidation, submitLabel = _a.submitLabel, cancelLabel = _a.cancelLabel, fromCalendarTable = _a.fromCalendarTable, toCalendarTable = _a.toCalendarTable, onSubmit = _a.onSubmit, onCancel = _a.onCancel, onSelectDate = _a.onSelectDate, onChangeCalendar = _a.onChangeCalendar, onCellRender = _a.onCellRender, onCalendarMount = _a.onCalendarMount, t = _a.t;
    var buttonFontSize = function () {
        switch (calendarSize) {
            case initCalendarSize.LARGE:
                return {
                    fontSize: '16px',
                    height: '40px',
                };
            case initCalendarSize.MEDIUM:
                return {
                    fontSize: '14px',
                    height: '36px',
                };
            case initCalendarSize.SMALL:
                return {
                    fontSize: '12px',
                    height: '32px',
                };
            case initCalendarSize.XSMALL:
                return {
                    fontSize: '11px',
                    height: '28px',
                };
            default:
                return {
                    fontSize: '14px',
                    height: '16px',
                };
        }
    };
    /**
     * calendar mount 감지
     */
    useEffect(function () {
        if (onCalendarMount) {
            onCalendarMount();
        }
    }, [onCalendarMount]);
    return (jsxs("div", __assign({ ref: ref, className: cx('date-range-picker-calendar', calendarSize) }, { children: [jsxs("div", __assign({ className: cx('calendar-area') }, { children: [jsx(Calendar, { calendarType: 'FROM', today: today, selectedFromDate: selectedFromDate, selectedToDate: selectedToDate, fromCalendarDate: fromCalendarDate, toCalendarDate: toCalendarDate, minDate: minDate, maxDate: maxDate, calendarSize: calendarSize, calendarTable: fromCalendarTable, onSelectDate: onSelectDate, onChangeCalendar: onChangeCalendar, onCellRender: onCellRender }), jsx(Calendar, { calendarType: 'TO', today: today, selectedFromDate: selectedFromDate, selectedToDate: selectedToDate, fromCalendarDate: fromCalendarDate, toCalendarDate: toCalendarDate, minDate: minDate, maxDate: maxDate, calendarSize: calendarSize, calendarTable: toCalendarTable, onSelectDate: onSelectDate, onChangeCalendar: onChangeCalendar, onCellRender: onCellRender })] })), jsxs("div", __assign({ className: cx('btn', calendarSize) }, { children: [jsx(Button, __assign({ type: 'none-border', onClick: onCancel, customStyle: buttonFontSize() }, { children: t ? t(cancelLabel) : cancelLabel })), jsx(Button, __assign({ disabled: !fromValidation || !toValidation, onClick: onSubmit, customStyle: buttonFontSize() }, { children: t ? t(submitLabel) : submitLabel }))] }))] })));
});
DateRangePickerCalendar.defaultProps = {
    onCellRender: undefined,
    onCalendarMount: undefined,
    t: undefined,
};

export { DateRangePickerCalendar as default };
//# sourceMappingURL=DateRangePickerCalendar.js.map
