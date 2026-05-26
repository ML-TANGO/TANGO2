import { __assign } from '../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import dayjs from '../../../../modules/dayjs/dayjs.min.js';
import { nowLocalTime } from '../../../utils/datetimeUtils.js';
import { theme } from '../../../utils/utils.js';
import classNames from '../../../../modules/classnames/bind.js';
import style from './Footer.module.scss.js';

var cx = classNames.bind(style);
var year = dayjs().year();
/**
 * Footer 컴포넌트
 */
function Footer(_a) {
    var theme = _a.theme, isOpen = _a.isOpen, LogoIcon = _a.logoIcon, copyrights = _a.copyrights, updated = _a.updated, language = _a.language;
    return (jsx("div", __assign({ className: cx('footer', theme, isOpen && 'open') }, { children: jsxs("div", __assign({ className: cx('box') }, { children: [jsx("div", __assign({ className: cx('logo') }, { children: typeof LogoIcon === 'function' ? (jsx(LogoIcon, {})) : (jsx("img", { src: LogoIcon ||
                            'https://via.placeholder.com/143x29.png?text=Logo+143x29', alt: 'Flightbase Logo' })) })), jsxs("div", __assign({ className: cx('items') }, { children: [jsx("span", __assign({ className: cx('copyrights') }, { children: copyrights })), jsx("span", __assign({ className: cx('updated') }, { children: updated && "Updated ".concat(updated) })), jsx("div", __assign({ className: cx('language') }, { children: language }))] }))] })) })));
}
Footer.defaultProps = {
    theme: theme.PRIMARY_THEME,
    isOpen: false,
    logoIcon: undefined,
    copyrights: "\u00A9 ".concat(year, " ACRYL inc. All rights reserved."),
    updated: nowLocalTime('YYYY.MM.DD'),
    language: undefined,
};

export { Footer as default };
//# sourceMappingURL=Footer.js.map
