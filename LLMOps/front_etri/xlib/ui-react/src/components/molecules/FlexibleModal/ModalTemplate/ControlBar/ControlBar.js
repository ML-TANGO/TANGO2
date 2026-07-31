import { __read, __assign } from '../../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import style from './ControlBar.module.scss.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import minimizeIcon from '../../../../../static/images/icons/ic-minimize-modal.svg.js';
import shrinkIcon from '../../../../../static/images/icons/ic-default-size-modal.svg.js';
import fullSizeIcon from '../../../../../static/images/icons/ic-full-size-modal.svg.js';
import closeIcon from '../../../../../static/images/icons/ic-close-modal.svg.js';
import { useState } from 'react';

var cx = classNames.bind(style);
var ButtonTooltip = function (_a) {
    var desc = _a.desc, visible = _a.visible;
    return (jsx("div", __assign({ className: cx('tooltip-container', visible ? 'visible' : 'hidden') }, { children: jsx("div", __assign({ className: cx('desc') }, { children: desc })) })));
};
function ControlBar(_a) {
    var minimize = _a.minimize, fullscreen = _a.fullscreen, isFullScreen = _a.isFullScreen, onClickClose = _a.onClickClose, onClickMinimize = _a.onClickMinimize, onClickFullScreen = _a.onClickFullScreen;
    /*
    onClick Function
    */
    var _b = __read(useState(false), 2), miniTip = _b[0], setMiniTip = _b[1];
    var _c = __read(useState(false), 2), fullTip = _c[0], setFullTip = _c[1];
    var _d = __read(useState(false), 2), closeTip = _d[0], setCloseTip = _d[1];
    var handleMinimize = function () { return onClickMinimize(); };
    var handleFullScreen = function () { return onClickFullScreen(); };
    var handleClose = function () { return onClickClose(); };
    return (jsxs("div", __assign({ className: cx('bar-container') }, { children: [jsx("div", { className: cx('left-side') }), jsxs("div", __assign({ className: cx('right-side') }, { children: [minimize && (jsxs("div", __assign({ className: cx('minimize'), onMouseEnter: function () { return setMiniTip(true); }, onMouseLeave: function () { return setMiniTip(false); }, onClick: function () { return handleMinimize(); } }, { children: [jsx("div", __assign({ className: cx('icon') }, { children: jsx("img", { src: minimizeIcon, alt: '\uCD5C\uC18C\uD654' }) })), jsx(ButtonTooltip, { desc: '\uD654\uBA74 \uCD5C\uC18C\uD654', visible: miniTip })] }))), fullscreen && (jsxs("div", __assign({ className: cx('full-size'), onClick: function () { return handleFullScreen(); }, onMouseEnter: function () { return setFullTip(true); }, onMouseLeave: function () { return setFullTip(false); } }, { children: [jsx("div", __assign({ className: cx('icon') }, { children: jsx("img", { src: isFullScreen ? shrinkIcon : fullSizeIcon, alt: '\uCD5C\uB300\uD654' }) })), jsx(ButtonTooltip, { desc: '\uC804\uCCB4 \uD654\uBA74\uC73C\uB85C \uBCF4\uAE30', visible: fullTip })] }))), jsxs("div", __assign({ className: cx('close'), onClick: function () {
                            handleClose();
                        }, onMouseEnter: function () { return setCloseTip(true); }, onMouseLeave: function () { return setCloseTip(false); } }, { children: [jsx("div", __assign({ className: cx('icon') }, { children: jsx("img", { src: closeIcon, alt: '\uB2EB\uAE30' }) })), jsx(ButtonTooltip, { desc: '\uB2EB\uAE30 (ESC)', visible: closeTip })] }))] }))] })));
}

export { ControlBar as default };
//# sourceMappingURL=ControlBar.js.map
