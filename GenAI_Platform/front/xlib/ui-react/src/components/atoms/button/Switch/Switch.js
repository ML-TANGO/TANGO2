import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import { SwitchSize, SwitchInit } from './types.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Switch.module.scss.js';

var cx = classNames.bind(style);
function Switch(_a) {
    var size = _a.size, checked = _a.checked, disabled = _a.disabled, label = _a.label, message = _a.message, customStyle = _a.customStyle, name = _a.name, onChange = _a.onChange, labelAlign = _a.labelAlign;
    return (jsx("div", __assign({ className: cx('jp', 'switch', size), title: message }, { children: jsxs("label", __assign({ className: cx('switch-container') }, { children: [labelAlign === 'left' && label && (jsx("div", __assign({ className: cx('combining-left') }, { children: label }))), jsx("input", { onChange: onChange, type: 'checkbox', checked: checked, disabled: disabled, name: name }), jsx("span", { style: customStyle }), labelAlign !== 'left' && label && (jsx("div", __assign({ className: cx('combining') }, { children: label })))] })) })));
}
Switch.defaultProps = {
    size: SwitchSize.MEDIUM,
    disabled: SwitchInit.disabled,
    label: undefined,
    message: undefined,
    customStyle: undefined,
    name: '',
    onChange: undefined,
    labelAlign: 'right',
};

export { Switch as default };
//# sourceMappingURL=Switch.js.map
