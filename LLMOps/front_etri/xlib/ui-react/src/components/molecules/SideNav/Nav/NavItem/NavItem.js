import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsx, jsxs, Fragment } from 'react/jsx-runtime';
import { theme } from '../../../../../utils/utils.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import style from './NavItem.module.scss.js';

var cx = classNames.bind(style);
function NavItem(_a) {
    var name = _a.name, path = _a.path, Icon = _a.icon, ActiveIcon = _a.activeIcon, group = _a.group, subGroup = _a.subGroup, isGroup = _a.isGroup, onNavigate = _a.onNavigate, theme = _a.theme;
    var target = path.split('/').slice(-1)[0];
    var currentPath = window.location.href;
    var end = currentPath.split('/').slice(-1)[0];
    // Flightbase: 메뉴 없는 상세 페이지 상위 메뉴에 매칭
    if (end === 'files') {
        end = 'datasets';
    }
    else if (end === 'test') {
        end = 'services';
    }
    else if (end === 'worker') {
        end = 'workers';
    }
    else if (['llmplayground', 'playgroundmonitor'].includes(end)) {
        end = 'llmplayground';
    }
    else if (['promptinfo', 'promptcommit'].includes(end)) {
        end = 'prompt';
    }
    return (jsx("div", __assign({ className: cx('nav-item', group && 'main-group', subGroup && 'sub-group', isGroup && 'group-head', theme, end === target && 'end-match') }, { children: onNavigate({
            element: (jsxs(Fragment, { children: [Icon &&
                        ActiveIcon &&
                        (typeof Icon === 'function' ? (jsxs("span", __assign({ className: cx('icon-wrap') }, { children: [jsx(ActiveIcon, { className: cx('active-ico') }), jsx(Icon, { className: cx('ico') })] }))) : (jsxs("span", __assign({ className: cx('icon-wrap') }, { children: [jsx("img", { className: cx('active-ico'), src: ActiveIcon, alt: "".concat(name, " link") }), jsx("img", { className: cx('ico'), src: Icon, alt: "".concat(name, " link") })] })))), jsx("span", __assign({ className: cx('text', isGroup && 'blue') }, { children: name }))] })),
            path: path,
            activeClassName: cx('active'),
            isActive: function (match) {
                if (match) {
                    var depth = match.path.split('/').length;
                    if (!match.isExact && depth === 4) {
                        return false;
                    }
                }
                return match !== null;
            },
        }) })));
}
NavItem.defaultProps = {
    theme: theme.PRIMARY_THEME,
};

export { NavItem as default };
//# sourceMappingURL=NavItem.js.map
