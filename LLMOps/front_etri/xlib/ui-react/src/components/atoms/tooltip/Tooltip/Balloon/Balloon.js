import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { useRef, useCallback, useEffect } from 'react';
import { tooltipType, verticalAlign, horizontalAlign } from '../types.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import style from './Balloon.module.scss.js';

var cx = classNames.bind(style);
function Balloon(_a) {
    var title = _a.title, contents = _a.contents, type = _a.type, isTail = _a.isTail, customStyle = _a.customStyle, contentsAlign = _a.contentsAlign, tooltipHandler = _a.tooltipHandler;
    var balloonRef = useRef(null);
    var handleClick = useCallback(function (e) {
        var _a;
        if (!((_a = balloonRef.current) === null || _a === void 0 ? void 0 : _a.contains(e.target))) {
            tooltipHandler();
        }
    }, [tooltipHandler]);
    useEffect(function () {
        document.addEventListener('click', handleClick, false);
        return function () {
            document.removeEventListener('click', handleClick, false);
        };
    }, [handleClick]);
    return (jsxs("div", __assign({ className: cx('balloon-wrap', type, contentsAlign === null || contentsAlign === void 0 ? void 0 : contentsAlign.vertical, contentsAlign === null || contentsAlign === void 0 ? void 0 : contentsAlign.horizontal, isTail ? 'tail' : 'pure'), style: customStyle, ref: balloonRef }, { children: [title && jsx("p", __assign({ className: cx('title') }, { children: title })), jsx("div", __assign({ className: cx('contents') }, { children: contents }))] })));
}
Balloon.defaultProps = {
    title: undefined,
    contents: undefined,
    type: tooltipType.LIGHT,
    isTail: false,
    customStyle: undefined,
    contentsAlign: {
        vertical: verticalAlign.BOTTOM,
        horizontal: horizontalAlign.LEFT,
    },
};

export { Balloon as default };
//# sourceMappingURL=Balloon.js.map
