import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx, Fragment } from 'react/jsx-runtime';
import { useRef, useState } from 'react';
import Balloon from './Balloon/Balloon.js';
import { iconAlign, verticalAlign, horizontalAlign, tooltipType } from './types.js';
import alert from '../../../../static/images/icons/00-ic-alert-info-o.svg.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Tooltip.module.scss.js';

var cx = classNames.bind(style);
function Tooltip(_a) {
    var children = _a.children, customStyle = _a.customStyle, icon = _a.icon, iconAlign = _a.iconAlign, label = _a.label, title = _a.title, contents = _a.contents, contentsAlign = _a.contentsAlign, globalCustomStyle = _a.globalCustomStyle, iconCustomStyle = _a.iconCustomStyle, labelCustomStyle = _a.labelCustomStyle, contentsCustomStyle = _a.contentsCustomStyle, type = _a.type, isTail = _a.isTail;
    var tooltipRef = useRef(null);
    var _b = __read(useState(false), 2), isOpen = _b[0], setIsOpen = _b[1];
    var tooltipHandler = function (flag) {
        if (flag === true || flag === false) {
            setIsOpen(flag);
        }
        else {
            setIsOpen(function (isOpen) { return !isOpen; });
        }
    };
    return (jsxs("div", __assign({ className: cx('tooltip-wrap'), ref: tooltipRef, style: globalCustomStyle }, { children: [jsx("div", __assign({ className: cx('tooltip-btn'), style: customStyle, onMouseOver: function () {
                    tooltipHandler(true);
                }, onMouseLeave: function () {
                    tooltipHandler(false);
                }, onTouchStart: function () {
                    tooltipHandler(true);
                }, onTouchEnd: function () {
                    tooltipHandler(false);
                } }, { children: !children ? (jsxs(Fragment, { children: [iconAlign === 'left' && (jsx("img", { src: icon, alt: 'icon', style: iconCustomStyle })), label && (jsx("label", __assign({ className: cx('label'), style: labelCustomStyle }, { children: label }))), iconAlign === 'right' && (jsx("img", { src: icon, alt: 'icon', style: iconCustomStyle }))] })) : (children) })), isOpen && (jsx(Balloon, { title: title, contents: contents, customStyle: contentsCustomStyle, contentsAlign: contentsAlign, type: type, isTail: isTail, tooltipHandler: tooltipHandler }))] })));
}
Tooltip.defaultProps = {
    children: undefined,
    customStyle: undefined,
    icon: alert,
    iconAlign: iconAlign.LEFT,
    label: undefined,
    title: undefined,
    contents: undefined,
    contentsAlign: {
        vertical: verticalAlign.BOTTOM,
        horizontal: horizontalAlign.LEFT,
    },
    globalCustomStyle: undefined,
    iconCustomStyle: undefined,
    labelCustomStyle: undefined,
    contentsCustomStyle: undefined,
    type: tooltipType.LIGHT,
    isTail: false,
};

export { Tooltip as default };
//# sourceMappingURL=Tooltip.js.map
