import { __rest, __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Textarea.module.scss.js';
import { TextareaStatus, TextareaSize } from './types.js';

var cx = classNames.bind(style);
function Textarea(_a) {
    var status = _a.status, size = _a.size, value = _a.value, name = _a.name, placeholder = _a.placeholder, isReadOnly = _a.isReadOnly, isDisabled = _a.isDisabled, customStyle = _a.customStyle, testId = _a.testId, theme = _a.theme, options = _a.options, maxLength = _a.maxLength, isShowMaxLength = _a.isShowMaxLength, autoFocus = _a.autoFocus, onChange = _a.onChange, t = _a.t, rest = __rest(_a, ["status", "size", "value", "name", "placeholder", "isReadOnly", "isDisabled", "customStyle", "testId", "theme", "options", "maxLength", "isShowMaxLength", "autoFocus", "onChange", "t"]);
    return (jsxs("div", __assign({ className: cx('jp', 'textarea', theme, size, status === TextareaStatus.ERROR && 'error') }, rest, { children: [isShowMaxLength && (jsxs("span", __assign({ className: cx('text-length-box', theme) }, { children: [jsx("span", __assign({ className: cx('text-length') }, { children: value ? value.length : 0 })), "/", maxLength] }))), jsx("textarea", __assign({ name: name, value: value, onChange: onChange, placeholder: t ? t(placeholder || '') : placeholder, readOnly: isReadOnly, disabled: isDisabled, "data-testid": testId, style: customStyle, maxLength: maxLength, autoFocus: autoFocus }, options))] })));
}
Textarea.defaultProps = {
    value: undefined,
    name: undefined,
    isDisabled: false,
    isReadOnly: false,
    placeholder: '',
    status: TextareaStatus.DEFAULT,
    size: TextareaSize.MEDIUM,
    customStyle: undefined,
    testId: undefined,
    theme: theme.PRIMARY_THEME,
    maxLength: 1000,
    isShowMaxLength: false,
    options: undefined,
    autoFocus: false,
    onChange: undefined,
    t: undefined,
};

export { Textarea as default };
//# sourceMappingURL=Textarea.js.map
