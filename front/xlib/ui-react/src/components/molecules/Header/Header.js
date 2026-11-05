import { __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { useEffect, Fragment } from 'react';
import { theme } from '../../../utils/utils.js';
import useWindowDimensions from '../../../hooks/useWindowDimensions.js';
import classNames from '../../../../modules/classnames/bind.js';
import style from './Header.module.scss.js';

var cx = classNames.bind(style);
/**
 * Header 컴포넌트
 */
function Header(_a) {
    var expandHandler = _a.expandHandler, hideMenuBtn = _a.hideMenuBtn, theme = _a.theme, leftBoxContents = _a.leftBoxContents, rightBoxContents = _a.rightBoxContents, isLogo = _a.isLogo, LogoIcon = _a.logoIcon;
    useEffect(function () { }, []);
    // 화면 너비
    var width = useWindowDimensions().width;
    // 반응형 사이드 네비게이션 기준 너비
    var reponsiveWidth = 1200;
    return (jsxs("div", __assign({ className: cx('header', theme) }, { children: [!hideMenuBtn && width <= reponsiveWidth && (jsx("div", __assign({ className: cx('left-box') }, { children: jsx("button", __assign({ id: 'side-menu-btn', "data-testid": 'side-menu-btn', className: cx('menu-btn'), onClick: expandHandler }, { children: jsxs("div", __assign({ className: cx('line-wrapper') }, { children: [jsx("div", { className: cx('line') }), jsx("div", { className: cx('line') }), jsx("div", { className: cx('line') })] })) })) }))), isLogo && (jsx("div", __assign({ className: cx('left-box') }, { children: jsx("h1", __assign({ className: cx('logo') }, { children: jsx("a", __assign({ href: '/' }, { children: typeof LogoIcon === 'function' ? (jsx(LogoIcon, {})) : (jsx("img", { className: cx('logo-img'), src: LogoIcon, alt: 'Flightbase Logo' })) })) })) }))), jsx("div", __assign({ className: cx('center-box') }, { children: leftBoxContents &&
                    leftBoxContents.map(function (ele, key) { return (jsx(Fragment, { children: ele }, key)); }) })), jsx("div", __assign({ className: cx('right-box') }, { children: rightBoxContents &&
                    rightBoxContents.map(function (ele, key) { return (jsx(Fragment, { children: ele }, key)); }) }))] })));
}
Header.defaultProps = {
    expandHandler: function () { },
    hideMenuBtn: false,
    theme: theme.PRIMARY_THEME,
    leftBoxContents: [],
    rightBoxContents: [],
    isLogo: false,
    logoIcon: 'https://via.placeholder.com/134x32.png?text=Logo+Widthx32',
};

export { Header as default };
//# sourceMappingURL=Header.js.map
