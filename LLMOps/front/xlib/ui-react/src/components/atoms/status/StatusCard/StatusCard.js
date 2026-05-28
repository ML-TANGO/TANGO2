import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { useState } from 'react';
import { theme } from '../../../../utils/utils.js';
import Balloon from './Balloon/Balloon.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './StatusCard.module.scss.js';

var cx = classNames.bind(style);
function StatusCard(_a) {
    var _b = _a.text, text = _b === void 0 ? '' : _b, status = _a.status, size = _a.size, type = _a.type, theme = _a.theme, customStyle = _a.customStyle, isTooltip = _a.isTooltip, tooltipData = _a.tooltipData, isProgressStatus = _a.isProgressStatus, rightIcon = _a.rightIcon, leftIcon = _a.leftIcon, leftIconStyle = _a.leftIconStyle, iconStyle = _a.iconStyle, iconOnMouseOver = _a.iconOnMouseOver, iconOnMouseLeave = _a.iconOnMouseLeave, tooltipComponent = _a.tooltipComponent, t = _a.t;
    var _c = __read(useState(false), 2), isOpen = _c[0], setIsOpen = _c[1];
    var onTooltipHandler = function (flag) {
        if (!isTooltip)
            return;
        if (flag === true || flag === false) {
            setIsOpen(flag);
        }
        else {
            setIsOpen(function (isOpen) { return !isOpen; });
        }
    };
    return (jsxs("div", __assign({ className: cx('jp', size) }, { children: [jsxs("div", __assign({ className: cx(status, type, theme), onMouseOver: function () {
                    onTooltipHandler(true);
                }, onMouseLeave: function () {
                    onTooltipHandler(false);
                }, style: customStyle }, { children: [leftIcon && (jsx("img", { style: leftIconStyle, className: cx('icon', isProgressStatus && 'progress'), src: leftIcon, alt: '' })), t ? t(text) : text, rightIcon && (jsx("img", { style: iconStyle, className: cx('icon', isProgressStatus && 'progress'), src: rightIcon, alt: '', onMouseOver: iconOnMouseOver, onMouseLeave: iconOnMouseLeave }))] })), isOpen &&
                (tooltipComponent ? tooltipComponent() : jsx(Balloon, __assign({}, tooltipData)))] })));
}
StatusCard.defaultProps = {
    status: 'running',
    text: '',
    size: 'medium',
    type: 'default',
    theme: theme.PRIMARY_THEME,
    customStyle: undefined,
    tooltipComponent: undefined,
    tooltipData: undefined,
    isProgressStatus: false,
    rightIcon: undefined,
    leftIcon: undefined,
    iconStyle: undefined,
    leftIconStyle: undefined,
    iconOnMouseOver: undefined,
    iconOnMouseLeave: undefined,
    isTooltip: false,
    t: undefined,
};

export { StatusCard as default };
//# sourceMappingURL=StatusCard.js.map
