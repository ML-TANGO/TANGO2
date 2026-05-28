import { __assign } from '../../../../_virtual/_tslib.js';
import { jsx, jsxs, Fragment } from 'react/jsx-runtime';
import { theme } from '../../../utils/utils.js';
import classNames from '../../../../modules/classnames/bind.js';
import { useRef, useContext, useCallback, useEffect } from 'react';
import { PageTemplateContext } from './context/context.js';
import style from './PageTemplate.module.scss.js';

var cx = classNames.bind(style);
var timer;
function PageTemplate(_a) {
    var headerRender = _a.headerRender, sideNavRender = _a.sideNavRender, slidePanelRender = _a.slidePanelRender, footerRender = _a.footerRender, contentRef = _a.contentRef, children = _a.children, theme = _a.theme;
    // 사이드 네비게이션 ref
    var navAreaRef = useRef(null);
    var frameRef = useRef(null);
    // 반응형 사이드 네비게이션 기준 너비
    var reponsiveWidth = 1200;
    // Context Hook
    // eslint-disable-next-line prettier/prettier
    var _b = useContext(PageTemplateContext), isOpen = _b.isOpen, pageTemplateDispatch = _b.pageTemplateDispatch;
    // Events
    var expandHandler = useCallback(function () {
        pageTemplateDispatch({ type: isOpen ? 'CLOSE' : 'OPEN' });
    }, [pageTemplateDispatch, isOpen]);
    // Effect Hook
    useEffect(function () {
        var handleClick = function (e) {
            var screenWidth = document.body.offsetWidth;
            if (isOpen &&
                !e.target.closest('#side-menu-btn') &&
                !e.target.closest('.sidenav') &&
                screenWidth < reponsiveWidth) {
                pageTemplateDispatch({ type: isOpen ? 'CLOSE' : 'OPEN' });
            }
        };
        // PopupMenu 컴포넌트가 마운트 될 때 documemnt에 팝업 닫기 이벤트 추가
        document.addEventListener('click', handleClick, false);
        return function () {
            // 현재 컴포넌트가 언마운트 되면 handleClick 이벤트 제거
            document.removeEventListener('click', handleClick, false);
        };
    }, [pageTemplateDispatch, isOpen]);
    useEffect(function () {
        var handleResize = function () {
            var openAttr;
            if (frameRef.current) {
                openAttr = frameRef.current.getAttribute('data-nav-open') === 'true';
            }
            else {
                return;
            }
            if (timer)
                return;
            timer = setTimeout(function () {
                var screenWidth = document.body.offsetWidth;
                if (screenWidth > reponsiveWidth && openAttr) {
                    pageTemplateDispatch({ type: 'OPEN' });
                }
                timer = undefined;
            }, 200);
        };
        window.addEventListener('resize', handleResize, true);
        return function () {
            // 현재 컴포넌트가 언마운트 되면 handleClick 이벤트 제거
            window.removeEventListener('resize', handleResize, false);
        };
    }, [pageTemplateDispatch, frameRef]);
    return (jsx("div", __assign({ className: cx('frame', isOpen && 'open', theme, !sideNavRender && 'no-nav'), ref: frameRef, "data-nav-open": isOpen }, { children: jsxs(Fragment, { children: [headerRender && (jsx("header", __assign({ className: cx('header-area') }, { children: headerRender(!sideNavRender, expandHandler) }))), sideNavRender && (jsx("div", __assign({ className: "sidenav ".concat(cx('sidenav-area', !headerRender && 'no-header')), ref: navAreaRef }, { children: sideNavRender() }))), jsxs("div", __assign({ className: cx('content-area', !headerRender && 'no-header'), ref: contentRef }, { children: [jsx("div", __assign({ className: cx('content', !headerRender && 'no-header', !footerRender && 'no-footer') }, { children: children })), footerRender && (jsx("footer", __assign({ className: cx('footer-area') }, { children: footerRender() })))] })), slidePanelRender, jsx("section", {})] }) })));
}
PageTemplate.defaultProps = {
    theme: theme.PRIMARY_THEME,
    headerRender: undefined,
    sideNavRender: undefined,
    footerRender: undefined,
    contentRef: null,
};

export { PageTemplate as default };
//# sourceMappingURL=PageTemplate.js.map
