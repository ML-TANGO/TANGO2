import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, Fragment, jsxs } from 'react/jsx-runtime';
import { useRef, useEffect } from 'react';
import classNames from '../../../../../modules/classnames/bind.js';
import ControlBar from './ControlBar/ControlBar.js';
import style from './ModalTemplate.module.scss.js';

var cx = classNames.bind(style);
function FlexibleModal(_a) {
    var size = _a.size, theme = _a.theme, control = _a.control, content = _a.content, modalKey = _a.modalKey, minimize = _a.minimize, fullscreen = _a.fullscreen, isMinimize = _a.isMinimize, isMaximize = _a.isMaximize, isFullScreen = _a.isFullScreen, onClickClose = _a.onClickClose, onClickMinimize = _a.onClickMinimize, onClickFullScreen = _a.onClickFullScreen;
    var modalRef = useRef(null);
    var containerRef = useRef(null);
    var minimizeRef = useRef(false);
    var handleClose = function () {
        if (onClickClose !== undefined)
            onClickClose(modalKey);
    };
    var handleMinimize = function () {
        if (onClickMinimize !== undefined)
            onClickMinimize(modalKey);
    };
    var handleFullScreen = function () {
        if (onClickFullScreen !== undefined)
            onClickFullScreen(modalKey);
    };
    var handleESC = function (e) {
        if (!minimizeRef.current && e.key === 'Escape')
            handleClose();
    };
    var checkControl = function () {
        if (control === undefined || control === null)
            return true;
        return control;
    };
    useEffect(function () {
        document.addEventListener('keydown', handleESC);
        return function () { return document.removeEventListener('keydown', handleESC); };
    }, []);
    useEffect(function () {
        if (isMinimize !== undefined)
            minimizeRef.current = isMinimize;
    }, [isMinimize]);
    return (jsx(Fragment, { children: jsx("div", __assign({ className: cx('shadow', isMinimize && 'hidden', isMaximize && 'visible'), ref: containerRef }, { children: jsxs("div", __assign({ className: cx(size !== null && size !== void 0 ? size : 'lg', theme, 'modal', isMinimize && 'hidden', isMaximize && 'visible', isFullScreen ? 'full-screen' : 'window'), ref: modalRef }, { children: [checkControl() && (jsx("div", __assign({ className: cx('modal-control') }, { children: jsx(ControlBar, { minimize: minimize !== null && minimize !== void 0 ? minimize : false, fullscreen: fullscreen !== null && fullscreen !== void 0 ? fullscreen : false, isFullScreen: isFullScreen !== null && isFullScreen !== void 0 ? isFullScreen : false, onClickClose: function () { return handleClose(); }, onClickMinimize: function () { return handleMinimize(); }, onClickFullScreen: function () { return handleFullScreen(); } }) }))), jsx("div", __assign({ className: cx('modal-content') }, { children: content }))] })) })) }));
}

export { FlexibleModal as default };
//# sourceMappingURL=ModalTemplate.js.map
