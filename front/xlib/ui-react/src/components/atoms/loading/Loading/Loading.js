import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import loadingIcon from '../../../../static/images/icons/spinner-1s-58.svg.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Loading.module.scss.js';

var cx = classNames.bind(style);
function Loading(_a) {
    var type = _a.type, size = _a.size, customStyle = _a.customStyle;
    if (type === 'circle') {
        return (jsx("div", { style: customStyle, className: cx('circle-loading', size) }));
    }
    return (jsx("div", __assign({ style: __assign(__assign({}, customStyle), { textAlign: 'center' }) }, { children: jsx("img", { src: loadingIcon, alt: 'Loading...' }) })));
}
Loading.defaultProps = {
    type: 'primary',
    size: 'small',
    customStyle: undefined,
};

export { Loading as default };
//# sourceMappingURL=Loading.js.map
