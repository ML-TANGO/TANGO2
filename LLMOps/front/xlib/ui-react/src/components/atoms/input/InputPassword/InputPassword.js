import { __assign, __read } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import ErrorIcon from '../../../../static/images/icons/00-ic-error.svg.js';
import hideIcon from '../../../../static/images/icons/00-ic-info-eye-off.svg.js';
import showIcon from '../../../../static/images/icons/00-ic-info-eye.svg.js';
import leftIcon from '../../../../static/images/icons/ic-lock.svg.js';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import { useRef, useState } from 'react';
import style from './InputPassword.module.scss.js';
import { InputStatus, InputSize } from './types.js';

var cx = classNames.bind(style);
function InputPassword(_a) {
    var status = _a.status, size = _a.size, name = _a.name, isDisabled = _a.isDisabled, isReadOnly = _a.isReadOnly, disableLeftIcon = _a.disableLeftIcon, disableShowBtn = _a.disableShowBtn, placeholder = _a.placeholder, value = _a.value, leftIcon = _a.leftIcon, customStyle = _a.customStyle, options = _a.options, tabIndex = _a.tabIndex, autoFocus = _a.autoFocus, testId = _a.testId, onChange = _a.onChange, onKeyPress = _a.onKeyPress, t = _a.t, theme = _a.theme;
    var inputRef = useRef(null);
    var inputAttr = __assign(__assign({}, options), { disabled: false, readOnly: false });
    // 비밀번호 보기/숨기기
    var _b = __read(useState(false), 2), passwordShown = _b[0], setPasswordShown = _b[1];
    var togglePassword = function () {
        setPasswordShown(!passwordShown);
    };
    if (isDisabled) {
        inputAttr.disabled = true;
    }
    else if (isReadOnly) {
        inputAttr.readOnly = true;
    }
    var paddingHandler = function () {
        if (disableLeftIcon && disableShowBtn) {
            return 'normal-padding';
        }
        if (!disableShowBtn && !disableLeftIcon) {
            return 'left-right-padding';
        }
        if (!disableShowBtn && disableLeftIcon) {
            return 'right-padding';
        }
        return 'left-padding';
    };
    return (jsxs("div", __assign({ className: cx('jp', 'input', size, status, !disableLeftIcon && 'left', theme) }, { children: [jsx("input", __assign({ className: cx(paddingHandler()), type: passwordShown ? 'text' : 'password', placeholder: t ? t(placeholder || '') : placeholder }, inputAttr, { value: value, onChange: onChange, onKeyPress: onKeyPress, ref: inputRef, style: __assign({}, customStyle), name: name, tabIndex: tabIndex, autoFocus: autoFocus, "data-testid": testId })), !disableLeftIcon && leftIcon && (jsx("img", { className: cx('visible-left-icon'), src: leftIcon, alt: '\uC544\uC774\uCF58' })), !disableShowBtn && (jsx("button", __assign({ className: cx('show-hide-btn'), onClick: togglePassword, tabIndex: -1 }, { children: jsx("img", { src: passwordShown ? showIcon : hideIcon, alt: 'show/hide' }) }))), status === 'error' && (jsx("img", { className: cx('pw-error-icon', disableShowBtn && 'right'), src: ErrorIcon, alt: 'error-icon' }))] })));
}
InputPassword.defaultProps = {
    status: InputStatus.DEFAULT,
    size: InputSize.MEDIUM,
    name: undefined,
    isDisabled: false,
    isReadOnly: false,
    disableLeftIcon: false,
    disableShowBtn: false,
    placeholder: undefined,
    value: undefined,
    leftIcon: leftIcon,
    customStyle: undefined,
    options: undefined,
    tabIndex: undefined,
    autoFocus: false,
    testId: undefined,
    onChange: undefined,
    onKeyPress: undefined,
    t: undefined,
    theme: theme.PRIMARY_THEME,
};

export { InputPassword as default };
//# sourceMappingURL=InputPassword.js.map
