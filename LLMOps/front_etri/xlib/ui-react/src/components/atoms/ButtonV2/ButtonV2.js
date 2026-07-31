import { __rest, __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import classNames from '../../../../modules/classnames/bind.js';
import Spinner from '../loading/Spinner/Spinner.js';
import style from './ButtonV2.module.scss.js';

var cx = classNames.bind(style);
var SPINNERCOLOR = {
    blue: 'white',
    white: 'primary',
    skyblue: 'primary',
    red: 'white',
    lightRed: 'red',
    gray: 'gray',
};
var calSpinnerColor = function (type, colorType) {
    if (type === 'outline')
        return 'paleGray';
    if (type === 'clear')
        return 'lightGray';
    if (!colorType)
        return 'primary';
    return SPINNERCOLOR[colorType];
};
var calPosition = function (label, icon, iconPosition, isLoading) {
    if (icon && iconPosition === 'left') {
        return (jsxs("div", __assign({ className: cx('content-cont', isLoading && 'isLoading') }, { children: [icon && (jsx("img", { className: cx('icon'), src: icon, alt: "".concat(label, "-icon") })), jsx("span", { children: label })] })));
    }
    if (icon && iconPosition === 'right') {
        return (jsxs("div", __assign({ className: cx('content-cont', isLoading && 'isLoading') }, { children: [jsx("span", { children: label }), icon && (jsx("img", { className: cx('icon'), src: icon, alt: "".concat(label, "-icon") }))] })));
    }
    return (jsx("span", __assign({ className: cx('content-cont', isLoading && 'isLoading') }, { children: label })));
};
function ButtonV2(_a) {
    var _b = _a.type, type = _b === void 0 ? 'solid' : _b, _c = _a.colorType, colorType = _c === void 0 ? 'blue' : _c, _d = _a.size, size = _d === void 0 ? 'm' : _d, children = _a.children, label = _a.label, icon = _a.icon, _e = _a.iconPosition, iconPosition = _e === void 0 ? 'left' : _e, _f = _a.isLoading, isLoading = _f === void 0 ? false : _f, _g = _a.disabled, disabled = _g === void 0 ? false : _g, _h = _a.boxShadow, boxShadow = _h === void 0 ? false : _h, props = __rest(_a, ["type", "colorType", "size", "children", "label", "icon", "iconPosition", "isLoading", "disabled", "boxShadow"]);
    var spinnerColor = calSpinnerColor(type, colorType);
    return (jsxs("button", __assign({ type: 'button', className: cx('button', type, colorType, size, icon && iconPosition === 'left' && 'icon-left', icon && iconPosition === 'right' && 'icon-right', boxShadow && type === 'clear' && 'with-box-shadow'), disabled: disabled }, props, { children: [isLoading && (jsx("div", __assign({ className: cx('spinner-cont') }, { children: jsx(Spinner, { size: 'sm', color: spinnerColor }) }))), children || calPosition(label, icon, iconPosition, isLoading)] })));
}

export { ButtonV2 as default };
//# sourceMappingURL=ButtonV2.js.map
