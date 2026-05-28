import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsxs, Fragment, jsx } from 'react/jsx-runtime';
import classNames from '../../../../../../modules/classnames/bind.js';
import style from './Balloon.module.scss.js';

var cx = classNames.bind(style);
function Balloon(_a) {
    var title = _a.title, description = _a.description;
    return (jsxs("div", __assign({ className: cx('balloon') }, { children: [title && (jsxs(Fragment, { children: [jsx("div", __assign({ className: cx('title') }, { children: title })), jsx("div", { className: cx('line') })] })), description && jsx("div", __assign({ className: cx('desc') }, { children: description }))] })));
}
Balloon.defaultProps = {
    title: undefined,
    description: undefined,
};

export { Balloon as default };
//# sourceMappingURL=Balloon.js.map
