import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { ButtonType, ButtonSize } from './types.js';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Button.module.scss.js';

var cx = classNames.bind(style);
var noop = function () { };
function Button(_a) {
    var type = _a.type, size = _a.size, theme = _a.theme, children = _a.children, disabled = _a.disabled, icon = _a.icon, iconAlign = _a.iconAlign, iconStyle = _a.iconStyle, customStyle = _a.customStyle, testId = _a.testId, title = _a.title, loading = _a.loading, _b = _a.btnType, btnType = _b === void 0 ? 'button' : _b, onClick = _a.onClick, onMouseOver = _a.onMouseOver, onMouseOut = _a.onMouseOut;
    if (icon) {
        return (jsxs("button", __assign({ className: cx('jp', 'btn', type, size, theme, "icon-".concat(iconAlign), loading && 'loading'), onClick: loading ? noop : onClick, style: customStyle, disabled: disabled, "data-testid": testId, title: title, onMouseOver: onMouseOver, onMouseOut: onMouseOut, type: btnType }, { children: [iconAlign === 'left' && (jsx("img", { className: cx('icon'), src: icon, style: iconStyle, alt: 'icon' })), children, iconAlign === 'right' && (jsx("img", { className: cx('icon'), src: icon, style: iconStyle, alt: 'icon' }))] })));
    }
    return (jsx("button", __assign({ className: cx('jp', 'btn', type, size, loading && 'loading', theme), onClick: loading ? noop : onClick, disabled: disabled, style: customStyle, "data-testid": testId, title: title, type: btnType, onMouseOver: onMouseOver, onMouseOut: onMouseOut }, { children: children })));
}
Button.defaultProps = {
    type: ButtonType.PRIMARY,
    size: ButtonSize.MEDIUM,
    theme: theme.PRIMARY_THEME,
    children: undefined,
    disabled: false,
    icon: undefined,
    iconAlign: 'left',
    iconStyle: undefined,
    btnType: 'button',
    customStyle: undefined,
    testId: undefined,
    title: undefined,
    loading: false,
    onClick: undefined,
    onMouseOver: undefined,
    onMouseOut: undefined,
};

export { Button as default };
//# sourceMappingURL=Button.js.map
