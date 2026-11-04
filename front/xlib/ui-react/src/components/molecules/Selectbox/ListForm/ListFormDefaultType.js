import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, jsxs } from 'react/jsx-runtime';
import { forwardRef, useRef, useEffect } from 'react';
import { theme, arrayToString } from '../../../../utils/utils.js';
import { useIntersectionObserver } from '../../../../hooks/useIntersectionObserver.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';

var cx = classNames.bind(style);
var ListFormDefaultType = forwardRef(function (_a, ref) {
    var type = _a.type, list = _a.list, selectedIdx = _a.selectedIdx, theme$1 = _a.theme, fontStyle = _a.fontStyle, backgroundColor = _a.backgroundColor, onSelect = _a.onSelect, onListController = _a.onListController, scrollObserver = _a.scrollObserver, t = _a.t;
    var testRef = useRef(null);
    var observer = useIntersectionObserver(testRef, {});
    useEffect(function () {
        if (scrollObserver &&
            !(observer === null || observer === void 0 ? void 0 : observer.isIntersecting) &&
            (observer === null || observer === void 0 ? void 0 : observer.isIntersecting) !== undefined) {
            scrollObserver(observer === null || observer === void 0 ? void 0 : observer.isIntersecting);
        }
    }, [observer, scrollObserver]);
    return (jsx("ul", __assign({ ref: ref, tabIndex: -1, onKeyDown: function (e) {
            onListController(e, type);
        }, className: cx(theme$1), style: {
            backgroundColor: backgroundColor,
        } }, { children: list.map(function (curMenu, idx) {
            var iconAlign = curMenu.iconAlign || 'left';
            var ref;
            if (list.length < 4 && idx === list.length - 1)
                ref = testRef;
            else if (idx === 4)
                ref = testRef;
            return (jsxs("li", __assign({ className: cx(selectedIdx === idx && theme$1 === theme.PRIMARY_THEME && 'hover', theme$1, curMenu.isDisable && 'disabled'), onClick: function (e) {
                    if (!curMenu.isDisable) {
                        onSelect(idx, e);
                    }
                }, style: {
                    backgroundColor: backgroundColor,
                }, ref: ref }, { children: [curMenu.icon && iconAlign === 'left' && (jsx("img", { src: curMenu.icon, className: cx('icon', 'left'), alt: 'list-icon', style: curMenu.iconStyle })), jsx("span", __assign({ style: fontStyle }, { children: arrayToString(curMenu.label, t) })), curMenu.icon && curMenu.iconAlign === 'right' && (jsx("img", { src: curMenu.icon, className: cx('icon', 'right'), alt: 'list-icon', style: curMenu.iconStyle })), curMenu.StatusIcon && (jsx("span", __assign({ className: cx('status') }, { children: jsx(curMenu.StatusIcon, {}) })))] }), "".concat(curMenu.value, "-").concat(idx)));
        }) })));
});
ListFormDefaultType.defaultProps = {
    fontStyle: undefined,
    backgroundColor: undefined,
    t: undefined,
};

export { ListFormDefaultType as default };
//# sourceMappingURL=ListFormDefaultType.js.map
