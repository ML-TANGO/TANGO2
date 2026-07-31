import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { Fragment } from 'react';
import styles from './ModalUnderBar.module.scss.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import ModalUnderBarItem from './UnderBarItem/ModalUnderBarItem.js';

var cx = classNames.bind(styles);
function ModalUnderBar(_a) {
    var modalList = _a.modalList;
    return (jsx("div", __assign({ className: cx('underbar-container') }, { children: modalList.map(function (modal, idx) {
            if (modal.isMinimize) {
                return (jsx(ModalUnderBarItem, { modal: modal }, "modal-under-item ".concat(modal.modalKey).concat(idx)));
            }
            return (jsx(Fragment, {}, "modal-under-item ".concat(modal.modalKey).concat(idx)));
        }) })));
}

export { ModalUnderBar as default };
//# sourceMappingURL=ModalUnderBar.js.map
