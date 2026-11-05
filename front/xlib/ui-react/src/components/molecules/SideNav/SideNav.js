import { __assign } from '../../../../_virtual/_tslib.js';
import { jsx, Fragment, jsxs } from 'react/jsx-runtime';
import IconDownloadBlue from '../../../static/images/icons/00-ic-data-download-blue.svg.js';
import { theme } from '../../../utils/utils.js';
import classNames from '../../../../modules/classnames/bind.js';
import React, { useMemo } from 'react';
import Nav from './Nav/Nav.js';
import style from './SideNav.module.scss.js';

var cx = classNames.bind(style);
/**
 * 사이드 네비게이션 컴포넌트
 */
function SideNav(_a) {
    var width = _a.width, mainNavComponent = _a.mainNavComponent, responsive = _a.responsive, theme = _a.theme, navList = _a.navList, mode = _a.mode, isManual = _a.isManual, isHideManual = _a.isHideManual, onNavigate = _a.onNavigate, footerRender = _a.footerRender, onServiceManual = _a.onServiceManual, t = _a.t;
    var styleObj = useMemo(function () {
        var obj = {};
        if (width && !responsive)
            obj.width = width;
        return obj;
    }, [width, responsive]);
    return (jsx(Fragment, { children: jsxs("section", __assign({ className: cx('sidenav', theme), style: styleObj }, { children: [mainNavComponent &&
                    React.cloneElement(mainNavComponent, {
                        children: (jsx("nav", __assign({ className: cx('nav') }, { children: jsx(Nav, { navList: navList, theme: theme, onNavigate: onNavigate, t: t }) }))),
                    }), footerRender ? (jsx("footer", { children: footerRender() })) : ((mode !== 'CUSTOM' || isManual) &&
                    !isHideManual &&
                    onServiceManual && (jsx("footer", __assign({ className: cx('sidenav-footer') }, { children: jsx("div", __assign({ className: cx('manual-box') }, { children: jsxs("button", __assign({ className: cx('manual-download-btn'), onClick: function () { return onServiceManual('Flightbase'); } }, { children: ["Service Manual", jsx("img", { className: cx('icon'), src: IconDownloadBlue, alt: 'download' })] })) })) }))))] })) }));
}
SideNav.defaultProps = {
    width: undefined,
    mainNavComponent: null,
    responsive: false,
    navList: [],
    mode: undefined,
    isManual: true,
    isHideManual: false,
    theme: theme.PRIMARY_THEME,
    onServiceManual: function () { },
    footerRender: undefined,
    t: undefined,
};

export { SideNav as default };
//# sourceMappingURL=SideNav.js.map
