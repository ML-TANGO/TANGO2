import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Radio.module.scss.js';

var cx = classNames.bind(style);
function Radio(_a) {
    var _b = _a.options, options = _b === void 0 ? [] : _b, selectedValue = _a.selectedValue, name = _a.name, customStyle = _a.customStyle, theme = _a.theme, testId = _a.testId, tooltipValue = _a.tooltipValue, isReadonly = _a.isReadonly, onTooltipRender = _a.onTooltipRender, onChange = _a.onChange, t = _a.t;
    return (jsx("div", __assign({ className: cx('jp', 'radio'), style: customStyle, "data-testid": testId }, { children: jsx("ul", { children: options.map(function (data, idx) {
                var label = data.label, value = data.value, disabled = data.disabled, icon = data.icon, labelStyle = data.labelStyle;
                var id = "".concat(idx, "-").concat(label, "-").concat(value);
                return (jsxs("li", { children: [jsx("input", { className: cx(theme), id: id, type: 'radio', name: name, disabled: (function () {
                                if (disabled) {
                                    return true;
                                }
                                if (isReadonly) {
                                    if (value === selectedValue) {
                                        return false;
                                    }
                                    return true;
                                }
                                return false;
                            })(), checked: value === selectedValue, value: value, onChange: onChange }), label && (jsxs("label", __assign({ htmlFor: id, style: labelStyle, className: cx(theme, (function () {
                                if (disabled) {
                                    return 'disabled';
                                }
                                if (isReadonly && value !== selectedValue) {
                                    return 'disabled';
                                }
                                return '';
                            })()) }, { children: [icon && (jsx("img", { className: cx('label-icon'), src: icon, alt: label || 'label' })), t ? t(label) : label] }))), onTooltipRender &&
                            tooltipValue !== undefined &&
                            tooltipValue.has(value) &&
                            onTooltipRender(value)] }, id));
            }) }) })));
}
Radio.defaultProps = {
    name: undefined,
    customStyle: undefined,
    theme: theme.PRIMARY_THEME,
    testId: undefined,
    tooltipValue: undefined,
    isReadonly: false,
    onTooltipRender: undefined,
    onChange: undefined,
    t: undefined,
};

export { Radio as default };
//# sourceMappingURL=Radio.js.map
