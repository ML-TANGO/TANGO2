import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { forwardRef } from 'react';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './DateRangePickerInput.module.scss.js';

var cx = classNames.bind(style);
var DateRangePickerInput = forwardRef(function (_a, ref) {
    var status = _a.status, inputSize = _a.inputSize, fromPlaceholder = _a.fromPlaceholder, toPlaceholder = _a.toPlaceholder, fromDate = _a.fromDate, toDate = _a.toDate, isReadonly = _a.isReadonly, isDisable = _a.isDisable, fromValidation = _a.fromValidation, toValidation = _a.toValidation, isOpenCalendar = _a.isOpenCalendar, customStyle = _a.customStyle, onOpenCalendar = _a.onOpenCalendar, onInputChange = _a.onInputChange, t = _a.t;
    return (jsxs("div", __assign({ className: cx(inputSize, status, isOpenCalendar && 'active', isReadonly && 'readonly', isDisable && 'disabled', (!fromValidation || !toValidation) && 'error'), ref: ref, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.inputForm }, { children: [jsx("input", { type: 'text', value: fromDate, onChange: function (e) {
                    onInputChange('FROM', e);
                }, onClick: onOpenCalendar, placeholder: t ? t(fromPlaceholder) : fromPlaceholder, readOnly: isReadonly, disabled: isDisable, onKeyDown: function (e) {
                    if (e.key === 'ArrowRight' &&
                        e.target.selectionStart === 10) {
                        var container = ref.current;
                        if (container) {
                            var toInput = container.childNodes[2];
                            toInput.focus();
                            toInput.setSelectionRange(0, 0);
                        }
                        e.preventDefault();
                    }
                }, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.inputFont }), jsx("span", { children: "~" }), jsx("input", { type: 'text', value: toDate, onChange: function (e) {
                    onInputChange('TO', e);
                }, onClick: onOpenCalendar, onKeyDown: function (e) {
                    if (toDate === '' && e.key === 'Backspace') {
                        var container = ref.current;
                        if (container) {
                            container.childNodes[0].focus();
                        }
                        return;
                    }
                    if (e.key === 'ArrowLeft' &&
                        e.target.selectionStart === 0) {
                        var container = ref.current;
                        if (container) {
                            var fromInput = container.childNodes[0];
                            fromInput.focus();
                            fromInput.setSelectionRange(fromInput.value.length, fromInput.value.length);
                        }
                        e.preventDefault();
                    }
                }, placeholder: t ? t(toPlaceholder) : toPlaceholder, readOnly: isReadonly, disabled: isDisable, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.inputFont })] })));
});
DateRangePickerInput.defaultProps = {
    customStyle: undefined,
    t: undefined,
};

export { DateRangePickerInput as default };
//# sourceMappingURL=DateRangePickerInput.js.map
