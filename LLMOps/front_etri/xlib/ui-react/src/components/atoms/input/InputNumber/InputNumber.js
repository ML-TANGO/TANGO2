import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import down from '../../../../static/images/icons/down.png.js';
import upIcon from '../../../../static/images/icons/up.png.js';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import { useState, useEffect } from 'react';
import style from './InputNumber.module.scss.js';
import { InputNumberStatus, InputNumberSize } from './types.js';

var cx = classNames.bind(style);
function InputNumber(_a) {
    var status = _a.status, size = _a.size, _b = _a.placeholder, placeholder = _b === void 0 ? '' : _b, isReadOnly = _a.isReadOnly, isDisabled = _a.isDisabled, value = _a.value, max = _a.max, min = _a.min, name = _a.name, _c = _a.step, step = _c === void 0 ? 1 : _c, upIcon = _a.upIcon, downIcon = _a.downIcon, customSize = _a.customSize, theme = _a.theme, disableIcon = _a.disableIcon, bottomTextExist = _a.bottomTextExist, error = _a.error, info = _a.info, _d = _a.valueAlign, valueAlign = _d === void 0 ? '' : _d, onChange = _a.onChange, onBlur = _a.onBlur, t = _a.t;
    var _e = __read(useState(''), 2), val = _e[0], setVal = _e[1];
    var onChangeData = function (value, e) {
        if (isReadOnly || isDisabled)
            return;
        if (max !== undefined && max < value) {
            setVal(String(max));
            if (onChange)
                onChange({
                    name: name,
                    value: max,
                    min: min,
                    max: max,
                    target: {
                        value: String(value),
                        name: name,
                        min: min,
                        max: max,
                    },
                }, e);
            return;
        }
        if (value !== '' && min !== undefined && min > value) {
            setVal(String(min));
            if (onChange)
                onChange({
                    name: name,
                    value: min,
                    min: min,
                    max: max,
                    target: {
                        value: String(value),
                        name: name,
                        min: min,
                        max: max,
                    },
                }, e);
            return;
        }
        setVal(String(value));
        if (onChange)
            onChange({
                name: name,
                value: value,
                min: min,
                max: max,
                target: {
                    value: String(value),
                    name: name,
                    min: min,
                    max: max,
                },
            }, e);
    };
    var onCountUp = function () {
        if (val === undefined) {
            setVal('0');
            onChangeData(0);
            return;
        }
        var temp = String(step).split('.');
        if (temp.length >= 2) {
            onChangeData((Number(val) + step).toFixed(temp[1].length));
        }
        else {
            onChangeData(Number(val) + step);
        }
    };
    var onCountDown = function () {
        if (val === undefined) {
            setVal('0');
            onChangeData(0);
            return;
        }
        var temp = String(step).split('.');
        if (temp.length >= 2) {
            onChangeData((Number(val) - step).toFixed(temp[1].length));
        }
        else {
            onChangeData(Number(val) - step);
        }
    };
    useEffect(function () {
        setVal(function () {
            if (typeof value !== 'number')
                return '';
            if (min !== undefined && value < min) {
                return String(min);
            }
            if (max !== undefined && value > max) {
                return String(max);
            }
            if (!Number.isNaN(value)) {
                return String(value);
            }
            return '';
        });
    }, [max, min, value]);
    return (jsxs("div", __assign({ className: cx('jp', 'input-number', isReadOnly && 'read-only', size, status === InputNumberStatus.ERROR && 'error', theme, disableIcon && 'disableIcon') }, { children: [jsx("input", { name: name, min: min, max: max, step: step, pattern: '[0-9]*', placeholder: t ? t(placeholder) : placeholder, value: val, disabled: isDisabled, readOnly: isReadOnly, style: customSize, onChange: function (e) {
                    if (isReadOnly || isDisabled)
                        return;
                    var val = e.target.value;
                    if (val === '-' || val === '') {
                        setVal(val);
                        onChangeData(val, e);
                        return;
                    }
                    var newVal = Number(val);
                    if (Number.isNaN(newVal)) {
                        if (val === '') {
                            setVal('');
                            onChangeData(val, e);
                        }
                        return;
                    }
                    if (val.length > 0 && val[val.length - 1] === '.') {
                        setVal(val);
                        onChangeData(val, e);
                        return;
                    }
                    setVal(val);
                    onChangeData(newVal, e);
                }, onWheel: function (e) { return e.currentTarget.blur(); }, onBlur: onBlur && onBlur, dir: "".concat(valueAlign === 'right' ? 'rtl' : '') }), !disableIcon && (jsxs("div", __assign({ className: cx('btn-box') }, { children: [upIcon && (jsx("button", __assign({ className: cx('up-btn'), onClick: onCountUp }, { children: jsx("img", { src: upIcon, alt: '\uC544\uC774\uCF58' }) }))), downIcon && (jsx("button", __assign({ className: cx('down-btn'), onClick: onCountDown }, { children: jsx("img", { src: downIcon, alt: '\uC544\uC774\uCF58' }) })))] }))), bottomTextExist && (jsxs("div", __assign({ className: cx('bottom-text') }, { children: [error && jsx("span", __assign({ className: cx('error') }, { children: error })), !error && info && jsx("span", __assign({ className: cx('info') }, { children: info }))] })))] })));
}
InputNumber.defaultProps = {
    status: InputNumberStatus.DEFAULT,
    size: InputNumberSize.MEDIUM,
    value: undefined,
    max: undefined,
    min: undefined,
    name: undefined,
    step: 1,
    isDisabled: false,
    isReadOnly: false,
    placeholder: '',
    upIcon: upIcon,
    downIcon: down,
    customSize: undefined,
    onChange: undefined,
    onBlur: undefined,
    t: undefined,
    theme: theme.PRIMARY_THEME,
    disableIcon: false,
    bottomTextExist: false,
    error: undefined,
    info: undefined,
    valueAlign: '',
};

export { InputNumber as default };
//# sourceMappingURL=InputNumber.js.map
