import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Badge.module.scss.js';

var cx = classNames.bind(style);
function Badge(_a) {
    var label = _a.label, type = _a.type, title = _a.title, size = _a.size, _b = _a.radius, radius = _b === void 0 ? 'default' : _b, leftIcon = _a.leftIcon, rightIcon = _a.rightIcon, customStyle = _a.customStyle;
    return (jsxs("span", __assign({ style: customStyle, className: cx('badge', type, size, radius), title: title }, { children: [leftIcon && jsx("span", __assign({ className: cx('icon', 'left') }, { children: leftIcon })), label, rightIcon && jsx("span", __assign({ className: cx('icon', 'right') }, { children: rightIcon }))] })));
}
Badge.defaultProps = {
    label: undefined,
    type: undefined,
    title: undefined,
    radius: 'default',
    size: 'sm',
    leftIcon: undefined,
    rightIcon: undefined,
    customStyle: undefined,
};

export { Badge as default };
//# sourceMappingURL=Badge.js.map
