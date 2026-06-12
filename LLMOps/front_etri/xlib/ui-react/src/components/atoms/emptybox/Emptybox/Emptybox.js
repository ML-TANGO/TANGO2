import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Emptybox.module.scss.js';

var cx = classNames.bind(style);
function Emptybox(_a) {
    var isBox = _a.isBox, customStyle = _a.customStyle, theme = _a.theme, _b = _a.text, text = _b === void 0 ? 'No Data' : _b, t = _a.t;
    return (jsx("div", __assign({ className: cx('no-data', isBox && 'box', theme), style: customStyle }, { children: t ? t(text) : text })));
}
Emptybox.defaultProps = {
    isBox: false,
    customStyle: undefined,
    text: '',
    theme: theme.PRIMARY_THEME,
    t: undefined,
};

export { Emptybox as default };
//# sourceMappingURL=Emptybox.js.map
