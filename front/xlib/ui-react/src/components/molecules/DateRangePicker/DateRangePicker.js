import { __read, __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, jsx, Fragment } from 'react/jsx-runtime';
import { useRef, useState, useCallback, useEffect, useLayoutEffect } from 'react';
import dayjs from '../../../../modules/dayjs/dayjs.min.js';
import DateRangePickerInput from './DateRangePickerInput/DateRangePickerInput.js';
import DateRangePickerSplitInput from './DateRangePickerSplitInput/DateRangePickerSplitInput.js';
import DateRangePickerCalendar from './DateRangePickerCalendar/DateRangePickerCalendar.js';
import { useComponentDidMount } from '../../../hooks/useComponentDidMount.js';
import { initDateRangePickerType, initDateRangePickerStatus, initInputSize, initCalendarSize } from './types.js';
import { DATE_FORM, MAXIMAL_TIME, MINIMAL_TIME, DATE_PATTERN, DATE_TIME_FORM } from '../../../utils/datetimeUtils.js';
import classNames from '../../../../modules/classnames/bind.js';
import style from './DateRangePicker.module.scss.js';

var cx = classNames.bind(style);
function DateRangePicker(_a) {
    var _b = _a.type, type = _b === void 0 ? initDateRangePickerType.PRIMARY : _b, _c = _a.status, status = _c === void 0 ? initDateRangePickerStatus.DEFAULT : _c, _d = _a.inputSize, inputSize = _d === void 0 ? initInputSize.MEDIUM : _d, _e = _a.calendarSize, calendarSize = _e === void 0 ? initCalendarSize.MEDIUM : _e, _f = _a.fromPlaceholder, fromPlaceholder = _f === void 0 ? '' : _f, _g = _a.toPlaceholder, toPlaceholder = _g === void 0 ? '' : _g, _h = _a.isDisabled, isDisabled = _h === void 0 ? false : _h, _j = _a.isReadOnly, isReadOnly = _j === void 0 ? false : _j, _k = _a.from, from = _k === void 0 ? dayjs().format(DATE_FORM) : _k, _l = _a.to, to = _l === void 0 ? dayjs().format(DATE_FORM) : _l, _m = _a.maxDate, maxDate = _m === void 0 ? MAXIMAL_TIME : _m, _o = _a.minDate, minDate = _o === void 0 ? MINIMAL_TIME : _o, _p = _a.today, today = _p === void 0 ? dayjs().format(DATE_FORM) : _p, _q = _a.submitLabel, submitLabel = _q === void 0 ? 'submit' : _q, _r = _a.cancelLabel, cancelLabel = _r === void 0 ? 'cancel' : _r, customStyle = _a.customStyle, onErrorMessage = _a.onErrorMessage, onCellRender = _a.onCellRender, onSubmit = _a.onSubmit, onCalendarMount = _a.onCalendarMount, onCalendarChangeDetector = _a.onCalendarChangeDetector, scrollHandler = _a.scrollHandler, t = _a.t;
    // from은 왼쪽 달력 to는 오른쪽 달력
    var inputRef = useRef(null);
    var fromInputRef = useRef(null);
    var toInputRef = useRef(null);
    var calendarRef = useRef(null);
    // submit 버튼 클릭 여부
    var _s = __read(useState(false), 2), isSubmit = _s[0], setIsSubmit = _s[1];
    // 달력 켜기 / 끄기 옵션
    var _t = __read(useState(false), 2), isOpenCalendar = _t[0], setIsOpenCalendar = _t[1];
    // input box에 보여지는 from, to 날짜
    var _u = __read(useState(from), 2), fromDate = _u[0], setFromDate = _u[1];
    var _v = __read(useState(to), 2), toDate = _v[0], setToDate = _v[1];
    // 선택되어있는 from, to 날짜 (미확정 데이터)
    var _w = __read(useState(from), 2), selectedFromDate = _w[0], setSelectedFromDate = _w[1];
    var _x = __read(useState(to), 2), selectedToDate = _x[0], setSelectedToDate = _x[1];
    // 달력 from, to 날짜
    var _y = __read(useState(from), 2), fromCalendarDate = _y[0], setFromCalendarDate = _y[1];
    var _z = __read(useState(to), 2), toCalendarDate = _z[0], setToCalendarDate = _z[1];
    var _0 = __read(useState(dayjs().format(DATE_FORM)), 2), prevFromDate = _0[0], setPrevFromDate = _0[1];
    var _1 = __read(useState(dayjs().format(DATE_FORM)), 2), prevToDate = _1[0], setPrevToDate = _1[1];
    // 달력 테이블
    var _2 = __read(useState([]), 2), fromCalendarTable = _2[0], setFromCalendarTable = _2[1];
    var _3 = __read(useState([]), 2), toCalendarTable = _3[0], setToCalendarTable = _3[1];
    // from날짜, to날짜 validation 체크
    var _4 = __read(useState(true), 2), fromValidation = _4[0], setFromValidation = _4[1];
    var _5 = __read(useState(true), 2), toValidation = _5[0], setToValidation = _5[1];
    /**
     * from이 to 이후 날짜일 경우 true
     * 정상 날짜 범위 false
     * @param from
     * @param to
     * @returns
     */
    var isSwitchDateRange = function (from, to) {
        var fDate = dayjs(from);
        var tDate = dayjs(to);
        if (fDate.isAfter(tDate)) {
            return true;
        }
        return false;
    };
    /**
     * 입력 받은 날짜 변환
     * @param from
     * @param to
     * @returns
     */
    var checkDate = useCallback(function (from, to) {
        if (isSwitchDateRange(from, to)) {
            return [to, from];
        }
        return [from, to];
    }, []);
    /**
     * 예외 사항 체크
     */
    var checkValidation = useCallback(function (from, to) { return function () {
        // from / to의 문자열 format이 양식과 맞지 않을 경우
        if (!DATE_PATTERN.test(from)) {
            setFromValidation(false);
            if (onErrorMessage)
                onErrorMessage("".concat(from, "\uC774 ").concat(DATE_FORM, " Form\uC774 \uC544\uB2D9\uB2C8\uB2E4."));
        }
        if (!DATE_PATTERN.test(to)) {
            setToValidation(false);
            if (onErrorMessage)
                onErrorMessage("".concat(to, "\uC774 ").concat(DATE_FORM, " Form\uC774 \uC544\uB2D9\uB2C8\uB2E4."));
        }
    }; }, [onErrorMessage]);
    /**
     * 달력으로 출력할 배열 계산
     */
    var calculateCalendar = useCallback(function (calendarType, date) {
        // calendarType이 from일때 왼쪽 달력, 아닐경우 오른쪽 달력
        var isFrom = calendarType === 'FROM';
        var d = dayjs(date);
        // 이전달
        var prevMonth = dayjs(d).subtract(1, 'month');
        // 이전달의 마지막날
        var prevLastDay = prevMonth.endOf('month');
        // 이전달 마지막날의 요일
        var prevLastDayOfWeek = prevLastDay.day();
        // 달력에 출력할 날짜
        var curDate = "".concat(prevLastDay.format('YYYY-MM'), "-").concat(Number(prevLastDay.format('DD')) - prevLastDayOfWeek);
        // 달력 배열
        var calendarObj = [];
        // 달력 배열 공간확보 (1주차 ~ 6주차)
        for (var i = 0; i < 6; i++) {
            calendarObj[i] = [];
        }
        for (var i = 0; i < 6; i++) {
            for (var j = 0; j < 7; j++) {
                calendarObj[i][j] = curDate;
                curDate = dayjs(curDate).add(1, 'day').format(DATE_FORM);
            }
        }
        if (isFrom) {
            setFromCalendarTable(calendarObj);
        }
        else {
            setToCalendarTable(calendarObj);
        }
    }, []);
    /**
     * inputbox를 클릭할 경우 달력 open
     */
    var onOpenCalendar = function (e) {
        if (!isReadOnly && !isDisabled) {
            setIsOpenCalendar(true);
        }
        if (!isOpenCalendar && scrollHandler) {
            e === null || e === void 0 ? void 0 : e.stopPropagation();
            scrollHandler();
        }
    };
    /**
     * 보여지는 달력 설정
     * @param {'FROM' | 'TO'} calendarType 달력 타입
     * @param {'BACK' | 'FRONT'} movePos 이전, 이후 달력 변경
     */
    var onChangeCalendar = function (calendarType, movePos) {
        var isFrom = calendarType === 'FROM';
        var isMoveBack = movePos === 'BACK';
        var date = isFrom ? dayjs(fromCalendarDate) : dayjs(toCalendarDate);
        var movedDate = isMoveBack
            ? date.subtract(1, 'month').format(DATE_FORM)
            : date.add(1, 'month').format(DATE_FORM);
        if (isFrom) {
            setFromCalendarDate(movedDate);
        }
        else {
            setToCalendarDate(movedDate);
        }
        calculateCalendar(calendarType, movedDate);
    };
    var calendarHandler = function (type, date) {
        if (type === 'FROM') {
            if (dayjs(fromCalendarDate).format('YYYYMM') !==
                dayjs(date).format('YYYYMM')) {
                setFromCalendarDate(date);
                calculateCalendar(type, date);
            }
        }
        else {
            if (dayjs(toCalendarDate).format('YYYYMM') !== dayjs(date).format('YYYYMM')) {
                setToCalendarDate(date);
                calculateCalendar(type, date);
            }
        }
    };
    /**
     * 날짜 선택
     * @param {string} date 클릭된 날짜
     */
    var onSelectDate = function (date, calendarType) {
        var filledDate = selectedFromDate !== '' && selectedToDate !== '';
        var nonFilledDate = selectedFromDate === '' && selectedToDate === '';
        var justFrom = selectedFromDate !== '' && selectedToDate === '';
        if (filledDate) {
            setFromDate(date);
            setSelectedFromDate(date);
            setToDate('');
            setSelectedToDate('');
            setFromValidation(true);
            setToValidation(false);
            calendarHandler(calendarType, date);
            return;
        }
        if (nonFilledDate) {
            setFromDate(date);
            setSelectedFromDate(date);
            setFromValidation(true);
            setToValidation(false);
            calendarHandler(calendarType, date);
            return;
        }
        if (justFrom) {
            if (isSwitchDateRange(selectedFromDate, date)) {
                setFromDate(date);
                setSelectedFromDate(date);
                setToDate(fromDate);
                setSelectedToDate(fromDate);
                setFromValidation(true);
                setToValidation(true);
            }
            else {
                setToDate(date);
                setSelectedToDate(date);
                setToValidation(true);
            }
        }
        calendarHandler(calendarType, date);
    };
    /**
     * input value 셋팅
     * @param {'FROM' | 'TO'} calendarType
     * @param {React.ChangeEvent<HTMLInputElement>} e
     */
    var onInputChange = function (calendarType, e) {
        var input = e.target.value;
        if (input.length > 10) {
            return;
        }
        if (calendarType === 'FROM') {
            setFromDate(input);
            if (!DATE_PATTERN.test(input)) {
                // 입력된 form 체크
                setFromValidation(false);
                if (onErrorMessage)
                    onErrorMessage("".concat(input, "\uC774 ").concat(DATE_FORM, " Form\uC774 \uC544\uB2D9\uB2C8\uB2E4."));
                return;
            }
            if (isSwitchDateRange(input, toDate)) {
                setFromValidation(false);
                if (onErrorMessage)
                    onErrorMessage("".concat(input, "\uC774 ").concat(toDate, " \uC774\uD6C4 \uB0A0\uC9DC\uC785\uB2C8\uB2E4."));
                return;
            }
            var iD_1 = dayjs(input);
            var mD_1 = dayjs(minDate);
            if (iD_1.isBefore(mD_1)) {
                if (onErrorMessage)
                    onErrorMessage("".concat(input, "\uC774 ").concat(minDate, " \uC774\uC804 \uB0A0\uC9DC\uC785\uB2C8\uB2E4."));
                return;
            }
            setFromValidation(true);
            setSelectedFromDate(input);
            // from 달력 변경
            setFromCalendarDate(input);
            calculateCalendar(calendarType, input);
            return;
        }
        setToDate(input);
        // 입력된 form 체크
        if (!DATE_PATTERN.test(input)) {
            setToValidation(false);
            if (onErrorMessage)
                onErrorMessage("".concat(input, "\uC774 ").concat(DATE_FORM, " Form\uC774 \uC544\uB2D9\uB2C8\uB2E4."));
            return;
        }
        if (isSwitchDateRange(fromDate, input)) {
            setToValidation(false);
            if (onErrorMessage)
                onErrorMessage("".concat(input, "\uC774 ").concat(fromDate, " \uC774\uC804 \uB0A0\uC9DC\uC785\uB2C8\uB2E4."));
            return;
        }
        var iD = dayjs(input);
        var mD = dayjs(maxDate);
        if (iD.isAfter(mD)) {
            if (onErrorMessage)
                onErrorMessage("".concat(input, "\uC774 ").concat(maxDate, " \uC774\uD6C4 \uB0A0\uC9DC\uC785\uB2C8\uB2E4."));
            return;
        }
        setToValidation(true);
        setSelectedToDate(input);
        // to 달력 변경
        setToCalendarDate(input);
        calculateCalendar(calendarType, input);
    };
    /**
     * from날짜, to날짜 calendar 렌더링 데이터 설정
     */
    var calendarRenderDateSet = useCallback(function (from, to, checkValidation) {
        calculateCalendar('FROM', from);
        calculateCalendar('TO', to);
        if (checkValidation)
            checkValidation();
    }, [calculateCalendar]);
    /**
     * cancel 버튼 클릭
     */
    var onCancel = useCallback(function () {
        setIsOpenCalendar(false);
        dateStateSet(prevFromDate, prevToDate);
        calendarRenderDateSet(prevFromDate, prevToDate);
        setFromValidation(true);
        setToValidation(true);
    }, [calendarRenderDateSet, prevFromDate, prevToDate]);
    /**
     * input 박스, 달력 영역 이외의 클릭이 감지될 경우
     */
    var onOutOfAreaClick = useCallback(function (e) {
        var _a, _b, _c, _d;
        if (isOpenCalendar &&
            !((_a = inputRef.current) === null || _a === void 0 ? void 0 : _a.contains(e.target)) &&
            !((_b = fromInputRef.current) === null || _b === void 0 ? void 0 : _b.contains(e.target)) &&
            !((_c = toInputRef.current) === null || _c === void 0 ? void 0 : _c.contains(e.target)) &&
            !((_d = calendarRef.current) === null || _d === void 0 ? void 0 : _d.contains(e.target))) {
            onCancel();
        }
    }, [isOpenCalendar, onCancel]);
    /**
     * 날짜 상태 설정
     * @param from
     * @param to
     */
    var dateStateSet = function (from, to) {
        setFromDate(from);
        setToDate(to);
        setFromCalendarDate(from);
        setToCalendarDate(to);
        setSelectedFromDate(from);
        setSelectedToDate(to);
    };
    /**
     * 컴포넌트 마운트시 실행
     */
    var componentDidMount = useCallback(function () {
        var _a = __read(checkDate(from, to), 2), f = _a[0], t = _a[1];
        calendarRenderDateSet(f, t, checkValidation(from, to));
    }, [checkDate, checkValidation, from, calendarRenderDateSet, to]);
    /**
     * 달력 날짜 Submit
     * @param e
     */
    var newSubmit = function (e) {
        setIsSubmit(true);
        if (onSubmit) {
            onSubmit(dayjs(selectedFromDate)
                .hour(0)
                .minute(0)
                .second(0)
                .format(DATE_TIME_FORM), dayjs(selectedToDate)
                .hour(23)
                .minute(59)
                .second(59)
                .format(DATE_TIME_FORM), e);
        }
        setFromDate(selectedFromDate);
        setToDate(selectedToDate);
        setFromCalendarDate(selectedFromDate);
        setToCalendarDate(selectedToDate);
        setIsOpenCalendar(false);
    };
    /**
     * 영역 클릭 이벤트
     */
    useEffect(function () {
        document.addEventListener('click', onOutOfAreaClick);
        return function () {
            document.removeEventListener('click', onOutOfAreaClick);
        };
    }, [onOutOfAreaClick]);
    /**
     * 달력 변경 감지
     */
    useLayoutEffect(function () {
        if (onCalendarChangeDetector) {
            onCalendarChangeDetector(fromCalendarDate, toCalendarDate);
        }
    }, [fromCalendarDate, onCalendarChangeDetector, toCalendarDate]);
    /**
     * mount validation 체크
     */
    useLayoutEffect(function () {
        var _a = __read(checkDate(from, to), 2), f = _a[0], t = _a[1];
        var min = dayjs(minDate);
        var max = dayjs(maxDate);
        dateStateSet(f, t);
        // minDate가 maxDate 이후 날짜일 경우
        if (max !== undefined && min.isAfter(max)) {
            setFromValidation(false);
            setToValidation(false);
            if (onErrorMessage)
                onErrorMessage("\uCD5C\uB300 \uB0A0\uC9DC [".concat(maxDate, "]\uAC00 \uCD5C\uC18C \uB0A0\uC9DC[").concat(minDate, "]\uBCF4\uB2E4 \uC791\uC2B5\uB2C8\uB2E4."));
        }
    }, [checkDate, from, maxDate, minDate, onErrorMessage, to]);
    /**
     * props에서 업데이트 된 날짜와 이전에 설정된 날짜가 다름
     * calendar 렌더링 데이터 재설정
     */
    useLayoutEffect(function () {
        if (isSubmit) {
            // submit 버튼 클릭시 날짜 바뀜 현상
            setIsSubmit(false);
        }
        else if (prevFromDate !== from || prevToDate !== to) {
            // submit 버튼을 누른게 아니면서 날짜가 바뀐 경우는 업데이트
            var _a = __read(checkDate(from, to), 2), f = _a[0], t_1 = _a[1];
            calendarRenderDateSet(f, t_1);
            setPrevFromDate(f);
            setPrevToDate(t_1);
        }
    }, [
        calendarRenderDateSet,
        from,
        prevFromDate,
        to,
        prevToDate,
        checkDate,
        isSubmit,
    ]);
    /**
     * 컴포넌트 mount 시 한번만 실행
     * calendar 렌더링 데이터 설정
     */
    useComponentDidMount(componentDidMount);
    return (jsxs("div", __assign({ className: cx('jp', 'date-range-picker'), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.globalForm }, { children: [jsxs("div", __assign({ className: cx('input-box', type === initDateRangePickerType.SPLIT_INPUT && 'split-input') }, { children: [type === initDateRangePickerType.PRIMARY && (jsx(DateRangePickerInput, { ref: inputRef, status: status, inputSize: inputSize, fromPlaceholder: fromPlaceholder, toPlaceholder: toPlaceholder, isReadonly: isReadOnly, isDisable: isDisabled, fromDate: fromDate, toDate: toDate, fromValidation: fromValidation, toValidation: toValidation, isOpenCalendar: isOpenCalendar, customStyle: customStyle === null || customStyle === void 0 ? void 0 : customStyle.primaryType, onInputChange: onInputChange, onOpenCalendar: onOpenCalendar, t: t })), type === initDateRangePickerType.SPLIT_INPUT && (jsxs(Fragment, { children: [jsx(DateRangePickerSplitInput, { ref: fromInputRef, calendarType: 'FROM', status: status, inputSize: inputSize, isReadOnly: isReadOnly, isDisabled: isDisabled, placeholder: fromPlaceholder, value: fromDate, isValidate: fromValidation, customStyle: customStyle === null || customStyle === void 0 ? void 0 : customStyle.splitType, onInputChange: onInputChange, onOpenCalendar: onOpenCalendar }), jsx(DateRangePickerSplitInput, { ref: toInputRef, calendarType: 'TO', status: status, inputSize: inputSize, isReadOnly: isReadOnly, isDisabled: isDisabled, placeholder: toPlaceholder, value: toDate, isValidate: toValidation, customStyle: customStyle === null || customStyle === void 0 ? void 0 : customStyle.splitType, onInputChange: onInputChange, onOpenCalendar: onOpenCalendar })] }))] })), isOpenCalendar && (jsx(DateRangePickerCalendar, { ref: calendarRef, today: today, selectedFromDate: selectedFromDate, selectedToDate: selectedToDate, fromCalendarDate: fromCalendarDate, toCalendarDate: toCalendarDate, fromValidation: fromValidation, toValidation: toValidation, fromCalendarTable: fromCalendarTable, toCalendarTable: toCalendarTable, minDate: minDate, maxDate: maxDate, calendarSize: calendarSize, submitLabel: submitLabel, cancelLabel: cancelLabel, onSubmit: newSubmit, onCancel: onCancel, onSelectDate: onSelectDate, onChangeCalendar: onChangeCalendar, onCellRender: onCellRender, onCalendarMount: onCalendarMount, t: t }))] })));
}
DateRangePicker.defaultProps = {
    type: initDateRangePickerType.PRIMARY,
    status: initDateRangePickerStatus.DEFAULT,
    inputSize: initInputSize.MEDIUM,
    calendarSize: initCalendarSize.MEDIUM,
    from: dayjs().format(DATE_FORM),
    to: dayjs().format(DATE_FORM),
    isDisabled: false,
    isReadOnly: false,
    fromPlaceholder: '',
    toPlaceholder: '',
    maxDate: MAXIMAL_TIME,
    minDate: MINIMAL_TIME,
    today: dayjs().format(DATE_FORM),
    submitLabel: 'submit',
    cancelLabel: 'cancel',
    customStyle: undefined,
    onErrorMessage: undefined,
    onCellRender: undefined,
    onSubmit: undefined,
    onCalendarMount: undefined,
    onCalendarChangeDetector: undefined,
    scrollHandler: undefined,
    t: undefined,
};

export { DateRangePicker as default };
//# sourceMappingURL=DateRangePicker.js.map
