import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import dayjs from '../../../../../../modules/dayjs/dayjs.min.js';
import left from '../../../../../static/images/icons/ic-left.svg.js';
import right from '../../../../../static/images/icons/ic-right.svg.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import style from './Calendar.module.scss.js';

var cx = classNames.bind(style);
Calendar.defaultProps = {
    onCellRender: undefined,
    t: undefined,
};
function Calendar(_a) {
    var calendarType = _a.calendarType, today = _a.today, fromCalendarDate = _a.fromCalendarDate, toCalendarDate = _a.toCalendarDate, selectedFromDate = _a.selectedFromDate, selectedToDate = _a.selectedToDate, minDate = _a.minDate, maxDate = _a.maxDate, calendarSize = _a.calendarSize, calendarTable = _a.calendarTable, onSelectDate = _a.onSelectDate, onChangeCalendar = _a.onChangeCalendar, onCellRender = _a.onCellRender, t = _a.t;
    var isFrom = calendarType === 'FROM';
    var min = dayjs(minDate);
    var max = dayjs(maxDate);
    var from = dayjs(selectedFromDate);
    var to = selectedToDate !== '' && dayjs(selectedToDate);
    var calendar = isFrom ? dayjs(fromCalendarDate) : dayjs(toCalendarDate);
    var y = calendar.year();
    var m = calendar.month();
    return (jsxs("div", __assign({ className: cx('calendar-wrap', calendarSize, isFrom ? 'from' : 'to') }, { children: [jsxs("div", __assign({ className: cx('calendar-controller') }, { children: [jsx("button", __assign({ className: cx('controll-btn', 'left'), onClick: function () {
                            onChangeCalendar(calendarType, 'BACK');
                        } }, { children: jsx("img", { src: left, alt: '< button' }) })), jsxs("span", __assign({ className: cx('current-date') }, { children: [String(y), ".", String(m + 1)] })), jsx("button", __assign({ className: cx('controll-btn', 'right'), onClick: function () {
                            onChangeCalendar(calendarType, 'FRONT');
                        } }, { children: jsx("img", { src: right, alt: '> button' }) }))] })), jsxs("div", __assign({ className: cx('calendar') }, { children: [jsxs("div", __assign({ className: cx('grid', 'head') }, { children: [jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('sun.label') : '일' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('mon.label') : '월' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('tue.label') : '화' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('thu.label') : '수' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('wed.label') : '목' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('fri.label') : '금' })), jsx("span", __assign({ className: cx('head-cell') }, { children: t ? t('sat.label') : '토' }))] })), calendarTable.map(function (week, i) { return (jsx("div", __assign({ className: cx('grid') }, { children: week.map(function (calendarDate, j) {
                            var selectedClass = '';
                            var fromClass = '';
                            var toClass = '';
                            var disabledClass = '';
                            var thisMonthClass = '';
                            var todayClass = '';
                            var justFrom = '';
                            var justTo = '';
                            var calendarDateObj = dayjs(calendarDate);
                            if (calendarDate === selectedFromDate) {
                                fromClass = 'from';
                                if (selectedToDate === '' && selectedFromDate) {
                                    justFrom = 'just-from';
                                }
                            }
                            if (calendarDate === selectedToDate) {
                                toClass = 'to';
                                if (selectedFromDate === '' && selectedToDate) {
                                    justTo = 'just-to';
                                }
                            }
                            // 오늘 날짜
                            if (today === calendarDate) {
                                todayClass = 'today';
                            }
                            // 선택된 기간 from 이후, to 이전 날짜
                            if (to && from < calendarDateObj && to > calendarDateObj) {
                                selectedClass = 'selected';
                                todayClass = '';
                            }
                            // 최소 날짜 이전 달력 날짜
                            if (min > calendarDateObj) {
                                disabledClass = 'disabled';
                            }
                            // 최대 날짜 이후 달력 날짜
                            if (max < calendarDateObj) {
                                disabledClass = 'disabled';
                            }
                            // 현재 년월과 달력날짜의 년월이 일치
                            if (y === calendarDateObj.year() &&
                                m === calendarDateObj.month()) {
                                thisMonthClass = 'this-month';
                            }
                            else {
                                selectedClass = '';
                                fromClass = '';
                                toClass = '';
                                todayClass = '';
                            }
                            // jsx element rendering (Optional)
                            if (onCellRender) {
                                return (jsx("span", __assign({ className: cx('custom-cell') }, { children: onCellRender(calendarDate, {
                                        selected: !(selectedClass === ''),
                                        from: !(fromClass === ''),
                                        to: !(toClass === ''),
                                        disabled: !(disabledClass === ''),
                                        thisMonth: !(thisMonthClass === ''),
                                        today: !(todayClass === ''),
                                        onClick: function () {
                                            if (disabledClass === '') {
                                                onSelectDate(calendarDate, calendarType);
                                            }
                                        },
                                    }) }), "".concat(i, "-").concat(j)));
                            }
                            return (jsx("span", __assign({ className: cx('cell', selectedClass, fromClass, toClass, justFrom, justTo, disabledClass, thisMonthClass, todayClass), onClick: function () {
                                    if (disabledClass === '') {
                                        onSelectDate(calendarDate, calendarType);
                                    }
                                } }, { children: jsx("span", __assign({ className: cx('inner-cell', fromClass, toClass) }, { children: Number(dayjs(calendarDate).format('DD')) })) }), "".concat(i, "-").concat(j)));
                        }) }), "".concat(calendarType, "-").concat(i))); })] }))] })));
}

export { Calendar as default };
//# sourceMappingURL=Calendar.js.map
