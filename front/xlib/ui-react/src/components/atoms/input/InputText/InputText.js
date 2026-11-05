import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import ErrorIcon from '../../../../static/images/icons/00-ic-error.svg.js';
import close from '../../../../static/images/icons/close-c.svg.js';
import darkLeftIcon from '../../../../static/images/icons/dark-search.svg.js';
import leftIcon from '../../../../static/images/icons/ic-search.svg.js';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import { useRef } from 'react';
import style from './InputText.module.scss.js';
import { InputStatus, InputSize } from './types.js';

var cx = classNames.bind(style);
var calRightBtnLocation = function (status, disableClearBtn, disableRightIcon) {
    if (status === 'error') {
        if (!disableClearBtn && !disableRightIcon)
            return 'depth2';
        if (!disableClearBtn && disableRightIcon)
            return 'depth1';
        if (disableClearBtn && !disableRightIcon)
            return 'depth1';
        return '';
    }
    if (!disableClearBtn && !disableRightIcon)
        return 'depth1';
    return '';
};
function InputText(_a) {
    var status = _a.status, size = _a.size, name = _a.name, isDisabled = _a.isDisabled, isReadOnly = _a.isReadOnly, disableClearBtn = _a.disableClearBtn, disableLeftIcon = _a.disableLeftIcon, disableRightIcon = _a.disableRightIcon, placeholder = _a.placeholder, value = _a.value, leftIcon = _a.leftIcon, rightIcon = _a.rightIcon, closeIcon = _a.closeIcon, customStyle = _a.customStyle, leftIconStyle = _a.leftIconStyle, rightIconStyle = _a.rightIconStyle, closeIconStyle = _a.closeIconStyle, options = _a.options, tabIndex = _a.tabIndex, onChange = _a.onChange, onClear = _a.onClear, onBlur = _a.onBlur, onKeyDown = _a.onKeyDown, autoFocus = _a.autoFocus, isLowercase = _a.isLowercase, theme = _a.theme, testId = _a.testId, t = _a.t;
    var inputRef = useRef(null);
    var inputAttr = __assign(__assign({}, options), { disabled: false, readOnly: false });
    var clearText = function () {
        if (onClear && inputRef.current) {
            inputRef.current.value = '';
            onClear(inputRef.current);
        }
    };
    if (isDisabled) {
        inputAttr.disabled = true;
    }
    else if (isReadOnly) {
        inputAttr.readOnly = true;
    }
    var paddingHandler = function () {
        if (status === 'error') {
            if (!disableLeftIcon) {
                if (!disableClearBtn && !disableRightIcon) {
                    return 'left-padding-right-tripple-padding';
                }
                if (disableClearBtn && !disableRightIcon) {
                    return 'left-padding-right-double-padding';
                }
                if (!disableClearBtn && disableRightIcon) {
                    return 'left-padding-right-double-padding';
                }
                return 'left-right-padding';
            }
            if (disableLeftIcon) {
                if (!disableClearBtn && !disableRightIcon) {
                    return 'right-tripple-padding';
                }
                if (disableClearBtn && !disableRightIcon) {
                    return 'right-double-padding';
                }
                if (!disableClearBtn && disableRightIcon) {
                    return 'right-double-padding';
                }
                return 'right-padding';
            }
            return 'normal-padding';
        }
        if (disableLeftIcon && disableClearBtn) {
            if (rightIcon) {
                return 'right-padding';
            }
            return 'normal-padding';
        }
        if (!disableClearBtn && !disableLeftIcon) {
            if (rightIcon) {
                return 'left-padding-right-double-padding';
            }
            return 'left-right-padding';
        }
        if (!disableClearBtn && disableLeftIcon) {
            if (rightIcon) {
                return 'right-double-padding';
            }
            return 'right-padding';
        }
        return 'left-padding';
    };
    return (jsxs("div", __assign({ className: cx('jp', 'input', theme, size, status, !disableLeftIcon && 'left') }, { children: [jsx("input", __assign({ className: cx(paddingHandler()), type: 'text', placeholder: t ? t(placeholder || '') : placeholder }, inputAttr, { value: value !== null && value !== void 0 ? value : '', onKeyDown: function (e) {
                    if (onKeyDown) {
                        onKeyDown(e);
                    }
                }, onChange: isLowercase
                    ? function (e) {
                        e.target.value = e.target.value.toLowerCase();
                        if (onChange) {
                            onChange(e);
                        }
                    }
                    : onChange, ref: inputRef, style: __assign({}, customStyle), name: name, autoFocus: autoFocus, autoComplete: 'off', tabIndex: tabIndex, "data-testid": testId, onBlur: onBlur && onBlur })), !disableLeftIcon && leftIcon && (jsx("img", { className: cx(disableLeftIcon ? 'disabled-left-icon' : 'visible-left-icon'), src: theme === 'jp-dark' ? darkLeftIcon : leftIcon, style: leftIconStyle, alt: 'left-icon' })), !disableClearBtn && value !== '' && !isDisabled && !isReadOnly && (jsx("button", __assign({ className: cx('close-btn', calRightBtnLocation(status, disableClearBtn, disableRightIcon)), onClick: clearText, style: closeIconStyle, tabIndex: -1 }, { children: jsx("img", { src: closeIcon, alt: 'close button' }) }))), !disableRightIcon && rightIcon && (jsx("img", { className: cx('right-icon', status === 'error' && 'exist-error-icon'), src: rightIcon, style: rightIconStyle, alt: 'right-icon' })), status === 'error' && (jsx("img", { className: cx('error-icon'), src: ErrorIcon, style: rightIconStyle, alt: 'error-icon' }))] })));
}
InputText.defaultProps = {
    status: InputStatus.DEFAULT,
    size: InputSize.MEDIUM,
    name: undefined,
    isDisabled: false,
    isReadOnly: false,
    disableClearBtn: true,
    disableLeftIcon: true,
    disableRightIcon: true,
    placeholder: undefined,
    value: undefined,
    leftIcon: leftIcon,
    rightIcon: undefined,
    closeIcon: close,
    customStyle: undefined,
    closeIconStyle: undefined,
    leftIconStyle: undefined,
    rightIconStyle: undefined,
    options: undefined,
    tabIndex: undefined,
    onClear: undefined,
    onChange: undefined,
    onKeyDown: undefined,
    onBlur: undefined,
    autoFocus: false,
    isLowercase: false,
    theme: theme.PRIMARY_THEME,
    testId: undefined,
    t: undefined,
};

export { InputText as default };
//# sourceMappingURL=InputText.js.map
