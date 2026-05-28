import { __rest, __assign, __awaiter, __generator } from '../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import ButtonV2 from '../../atoms/ButtonV2/ButtonV2.js';
import popupCloseIcon from '../../../static/images/icons/00-ic-close.svg.js';
import classNames from '../../../../modules/classnames/bind.js';
import React, { useRef, useEffect } from 'react';
import style from './Popup.module.scss.js';

var cx = classNames.bind(style);
var calSubmitButtonType = function (type) {
    if (type === 'main')
        return 'blue';
    if (type === 'delete')
        return 'red';
    return 'blue';
};
var calPopupContents = function (popupContents) {
    if (!popupContents)
        return '';
    if (typeof popupContents !== 'string')
        return popupContents;
    return popupContents.split('\n').map(function (line, index) { return (jsxs(React.Fragment, { children: [line, jsx("br", {})] }, index)); });
};
var handleSubmitBtn = function (isLoading, handleSubmit) {
    if (isLoading)
        return;
    if (typeof handleSubmit === 'function') {
        handleSubmit(); // 타입 안전성을 높이기 위해 타입 체크
    }
};
function Popup(_a) {
    var _this = this;
    var _b = _a.type, type = _b === void 0 ? 'main' : _b, _c = _a.isLoading, isLoading = _c === void 0 ? false : _c, _d = _a.isAnimation, isAnimation = _d === void 0 ? false : _d, frontTitle = _a.frontTitle, popupTitle = _a.popupTitle, popupContents = _a.popupContents, _e = _a.cancelBtnLabel, cancelBtnLabel = _e === void 0 ? '취소' : _e, _f = _a.submitBtnLabel, submitBtnLabel = _f === void 0 ? '확인' : _f, handleCancel = _a.handleCancel, handleSubmit = _a.handleSubmit, props = __rest(_a, ["type", "isLoading", "isAnimation", "frontTitle", "popupTitle", "popupContents", "cancelBtnLabel", "submitBtnLabel", "handleCancel", "handleSubmit"]);
    var submitBtnColor = calSubmitButtonType(type);
    var checkLinePopupConetents = calPopupContents(popupContents);
    // ** isAnimation **
    var modalRef = useRef(null);
    useEffect(function () {
        // eslint-disable-next-line no-useless-return
        if (!isAnimation)
            return;
        var modalEle = modalRef.current;
        var timeoutId = null;
        if (modalEle) {
            timeoutId = setTimeout(function () {
                modalEle.style.opacity = '1';
            }, 1);
        }
        // eslint-disable-next-line consistent-return
        return function () {
            if (modalEle) {
                modalEle.style.opacity = '0';
            }
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        };
    }, [isAnimation, modalRef]);
    useEffect(function () {
        var handleKeyDown = function (event) { return __awaiter(_this, void 0, void 0, function () {
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (!(event.key === 'Escape')) return [3 /*break*/, 1];
                        handleCancel(); // ESC로 취소
                        return [3 /*break*/, 3];
                    case 1:
                        if (!(event.key === 'Enter')) return [3 /*break*/, 3];
                        return [4 /*yield*/, handleSubmit()];
                    case 2:
                        _a.sent(); // Enter로 확인
                        _a.label = 3;
                    case 3: return [2 /*return*/];
                }
            });
        }); };
        window.addEventListener('keydown', handleKeyDown);
        return function () {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [handleCancel, handleSubmit]);
    return (jsxs("section", __assign({ ref: modalRef, className: cx('popup', type, isAnimation && 'animation') }, props, { children: [jsx("div", __assign({ className: cx('header-cont') }, { children: jsx("button", __assign({ className: cx('close-btn'), onClick: handleCancel }, { children: jsx("img", { className: cx('close-img'), src: popupCloseIcon, alt: 'close-icon' }) })) })), jsxs("div", __assign({ className: cx('contents-cont') }, { children: [jsxs("div", __assign({ className: cx('title-cont') }, { children: [frontTitle && frontTitle, jsx("h2", __assign({ className: cx('popup-title') }, { children: popupTitle }))] })), jsx("div", __assign({ className: cx('popup-contents', type === 'sub' && 'sub') }, { children: checkLinePopupConetents }))] })), jsxs("div", __assign({ className: cx('btn-cont', type === 'sub' && 'sub') }, { children: [type !== 'sub' && (jsx(ButtonV2, { onClick: handleCancel, type: 'clear', size: 'l', colorType: 'gray', label: cancelBtnLabel })), jsx(ButtonV2, { size: 'l', label: submitBtnLabel, onClick: function () { return handleSubmitBtn(isLoading, handleSubmit); }, colorType: submitBtnColor, isLoading: isLoading })] }))] })));
}

export { Popup as default };
//# sourceMappingURL=Popup.js.map
