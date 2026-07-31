import { __assign } from '../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import { useRef, useEffect } from 'react';
import { theme } from '../../../utils/utils.js';
import classNames from '../../../../modules/classnames/bind.js';
import style from './Modal.module.scss.js';

var cx = classNames.bind(style);
function Modal(_a) {
    var HeaderRender = _a.HeaderRender, ContentRender = _a.ContentRender, FooterRender = _a.FooterRender, headerProps = _a.headerProps, footerProps = _a.footerProps, contentProps = _a.contentProps, windowStyle = _a.windowStyle, headerStyle = _a.headerStyle, contentStyle = _a.contentStyle, footerStyle = _a.footerStyle, topAnimation = _a.topAnimation, theme = _a.theme;
    var modalRef = useRef(null);
    useEffect(function () {
        var modalEle = modalRef.current;
        // 애니메이션
        setTimeout(function () {
            if (modalEle) {
                modalEle.style.top = topAnimation || '0';
                modalEle.style.opacity = '1';
            }
        }, 1);
        return function () {
            if (modalEle) {
                modalEle.style.top = '0';
                modalEle.style.opacity = '0';
            }
        };
    }, [topAnimation]);
    return (jsx("div", __assign({ className: cx('shadow') }, { children: jsxs("div", __assign({ className: cx('modal', theme), ref: modalRef, style: windowStyle }, { children: [HeaderRender && (jsx("div", __assign({ className: cx('modal-header'), style: headerStyle }, { children: jsx(HeaderRender, __assign({}, headerProps)) }))), ContentRender && (jsx("div", __assign({ className: cx('modal-content'), style: contentStyle }, { children: jsx(ContentRender, __assign({}, contentProps)) }))), FooterRender && (jsx("div", __assign({ className: cx('modal-footer'), style: footerStyle }, { children: jsx(FooterRender, __assign({}, footerProps)) })))] })) })));
}
Modal.defaultProps = {
    HeaderRender: undefined,
    ContentRender: undefined,
    FooterRender: undefined,
    headerProps: undefined,
    footerProps: undefined,
    contentProps: undefined,
    windowStyle: undefined,
    headerStyle: undefined,
    contentStyle: undefined,
    footerStyle: undefined,
    topAnimation: '0',
    theme: theme.PRIMARY_THEME,
};

export { Modal as default };
//# sourceMappingURL=Modal.js.map
