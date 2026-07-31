import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { forwardRef } from 'react';
import { initDateRangePickerStatus, initInputSize } from '../types.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './DateRangePickerSplitInput.module.scss.js';

var cx = classNames.bind(style);
var DateRangePickerSplitInput = forwardRef(function (_a, ref) {
    var _b = _a.status, status = _b === void 0 ? initDateRangePickerStatus.DEFAULT : _b, _c = _a.inputSize, inputSize = _c === void 0 ? initInputSize.MEDIUM : _c, placeholder = _a.placeholder, calendarType = _a.calendarType, _d = _a.value, value = _d === void 0 ? '' : _d, isValidate = _a.isValidate, isDisabled = _a.isDisabled, isReadOnly = _a.isReadOnly, customStyle = _a.customStyle, onOpenCalendar = _a.onOpenCalendar, onInputChange = _a.onInputChange, t = _a.t;
    return (jsx("input", { className: cx(inputSize, !isValidate ? 'error' : status), type: 'text', placeholder: t && placeholder ? t(placeholder) : placeholder, disabled: isDisabled, readOnly: isReadOnly, onChange: function (e) {
            onInputChange(calendarType, e);
        }, onClick: onOpenCalendar, autoComplete: 'off', name: calendarType, ref: ref, value: value, style: __assign(__assign({}, customStyle === null || customStyle === void 0 ? void 0 : customStyle.inputForm), customStyle === null || customStyle === void 0 ? void 0 : customStyle.inputFont) }));
});
DateRangePickerSplitInput.defaultProps = {
    customStyle: undefined,
    t: undefined,
};

export { DateRangePickerSplitInput as default };
//# sourceMappingURL=DateRangePickerSplitInput.js.map
