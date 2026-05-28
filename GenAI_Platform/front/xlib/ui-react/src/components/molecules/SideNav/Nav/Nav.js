import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Nav.module.scss.js';
import NavItem from './NavItem/NavItem.js';

var cx = classNames.bind(style);
function Nav(_a) {
    var _b = _a.navList, navList = _b === void 0 ? [] : _b, theme = _a.theme, onNavigate = _a.onNavigate, t = _a.t;
    return (jsx("div", __assign({ className: cx('nav-list', theme) }, { children: navList.map(function (_a, key) {
            var name = _a.name, path = _a.path, Icon = _a.icon, ActiveIcon = _a.activeIcon, group = _a.group, subGroup = _a.subGroup, isGroup = _a.isGroup, isFirstGroup = _a.isFirstGroup, isLastGroup = _a.isLastGroup, disabled = _a.disabled;
            return !disabled ? (jsx("div", __assign({ className: cx('nav-wrap', group && 'main-group', subGroup && 'sub-group', isFirstGroup && 'first-group', isLastGroup && 'last-group') }, { children: jsx(NavItem, { name: t ? t(name) : name, path: path, icon: Icon, activeIcon: ActiveIcon, isGroup: isGroup, group: group, subGroup: subGroup, theme: theme, onNavigate: onNavigate }, key) }), key)) : null;
        }) })));
}
Nav.defaultProps = {
    navList: [],
    theme: theme.PRIMARY_THEME,
    t: undefined,
};

export { Nav as default };
//# sourceMappingURL=Nav.js.map
