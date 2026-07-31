import { __assign } from '../../../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import styles from './ModalUnderBarItem.module.scss.js';
import classNames from '../../../../../../../modules/classnames/bind.js';
import maximizeIcon from '../../../../../../static/images/icons/ic-maximize-modal.svg.js';
import closeIcon from '../../../../../../static/images/icons/ic-close-modal.svg.js';

var cx = classNames.bind(styles);
function ModalUnderBarItem(_a) {
    var _b;
    var modal = _a.modal;
    var onClickClose = modal.onClickClose, onClickMaximize = modal.onClickMaximize;
    var handleClose = function () {
        onClickClose(modal.modalKey);
    };
    var handleMaximize = function () {
        if (onClickMaximize !== undefined)
            onClickMaximize(modal.modalKey);
    };
    var handleDoubleClick = function () {
        if (onClickMaximize !== undefined)
            onClickMaximize(modal.modalKey);
    };
    return (jsxs("div", __assign({ className: cx('underbar-item'), onDoubleClick: function () {
            handleDoubleClick();
        } }, { children: [jsx("div", __assign({ className: cx('modal-title') }, { children: (_b = modal.title) !== null && _b !== void 0 ? _b : modal.modalKey })), jsxs("div", __assign({ className: cx('control-icons') }, { children: [jsx("div", __assign({ className: cx('maximize') }, { children: jsx("img", { onClick: function () {
                                handleMaximize();
                            }, src: maximizeIcon, alt: '\uCD5C\uB300\uD654' }) })), jsx("div", __assign({ className: cx('close') }, { children: jsx("img", { src: closeIcon, alt: '\uB2EB\uAE30', onClick: function () { return handleClose(); } }) }))] }))] })));
}

export { ModalUnderBarItem as default };
//# sourceMappingURL=ModalUnderBarItem.js.map
