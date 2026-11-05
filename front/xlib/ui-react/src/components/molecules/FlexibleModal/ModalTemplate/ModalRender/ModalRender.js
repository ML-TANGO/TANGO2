import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsxs, Fragment, jsx } from 'react/jsx-runtime';
import FlexibleModal from '../ModalTemplate.js';
import ModalUnderBar from '../ModalUnderBar/ModalUnderBar.js';

function ModalRender(_a) {
    var modalList = _a.modalList;
    return (jsxs(Fragment, { children: [modalList.map(function (modal, idx) {
                return jsx(FlexibleModal, __assign({}, modal), "".concat(modal.modalKey).concat(idx));
            }), jsx(ModalUnderBar, { modalList: modalList })] }));
}

export { ModalRender as default };
//# sourceMappingURL=ModalRender.js.map
