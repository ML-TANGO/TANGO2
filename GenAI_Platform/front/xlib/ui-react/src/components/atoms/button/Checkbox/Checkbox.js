import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Checkbox.module.scss.js';

var cx = classNames.bind(style);
function Checkbox(_a) {
    var label = _a.label, checked = _a.checked, disabled = _a.disabled, customLabelStyle = _a.customLabelStyle, customStyle = _a.customStyle, onChange = _a.onChange, theme = _a.theme, name = _a.name, value = _a.value;
    return (jsx("div", __assign({ className: cx('jp', 'checkbox') }, { children: jsxs("label", __assign({ className: cx('check-container'), style: customStyle }, { children: [jsx("input", { onChange: onChange, type: 'checkbox', checked: checked, disabled: disabled, name: name, value: value }), jsx("span", { className: cx('checkmark', theme), style: {
                        borderColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.borderColor,
                        backgroundColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.backgroundColor,
                    } }), label && (jsx("div", __assign({ className: cx('combining', disabled && 'disabled'), style: customLabelStyle }, { children: label })))] })) })));
}
Checkbox.defaultProps = {
    checked: false,
    disabled: false,
    label: undefined,
    onChange: undefined,
    theme: theme.PRIMARY_THEME,
    customLabelStyle: undefined,
    customStyle: undefined,
    name: undefined,
    value: undefined,
};

export { Checkbox as default };
//# sourceMappingURL=Checkbox.js.map
