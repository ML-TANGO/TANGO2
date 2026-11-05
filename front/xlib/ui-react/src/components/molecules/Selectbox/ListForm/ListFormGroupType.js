import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx, jsxs, Fragment } from 'react/jsx-runtime';
import { forwardRef } from 'react';
import { arrayToString } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';

var cx = classNames.bind(style);
var ListFormGroupType = forwardRef(function (_a, ref) {
    var type = _a.type, list = _a.list, selectedIdx = _a.selectedIdx, fontStyle = _a.fontStyle, theme = _a.theme, backgroundColor = _a.backgroundColor, onSelect = _a.onSelect, onListController = _a.onListController, t = _a.t;
    return (jsx("ul", __assign({ ref: ref, tabIndex: -1, onKeyDown: function (e) {
            onListController(e, type);
        }, className: cx(theme), style: {
            backgroundColor: backgroundColor,
        } }, { children: list.map(function (curMenu, idx) {
            var iconAlign = curMenu.iconAlign || 'left';
            return (jsx("li", __assign({ className: cx(selectedIdx === idx && 'hover', curMenu.isTitle && 'title'), onClick: function (e) {
                    if (!curMenu.isTitle)
                        onSelect(idx, e);
                } }, { children: curMenu.isTitle ? (jsxs(Fragment, { children: [curMenu.icon && iconAlign === 'left' && (jsx("img", { className: cx('icon', 'left', 'title'), src: curMenu.icon, alt: 'list-icon', style: curMenu.iconStyle })), idx > 0 && jsx("div", { className: cx('divide-line') }), jsx("span", __assign({ className: cx('title-label'), style: fontStyle }, { children: arrayToString(curMenu.label, t) })), curMenu.icon && curMenu.iconAlign === 'right' && (jsx("img", { src: curMenu.icon, alt: 'list-icon', className: cx('icon', 'right', 'title'), style: curMenu.iconStyle }))] })) : (jsxs(Fragment, { children: [curMenu.icon && iconAlign === 'left' && (jsx("img", { src: curMenu.icon, alt: 'list-icon', className: cx('icon', 'left'), style: curMenu.iconStyle })), jsx("span", __assign({ style: fontStyle }, { children: arrayToString(curMenu.label, t) })), curMenu.icon && curMenu.iconAlign === 'right' && (jsx("img", { className: cx('icon', 'right'), src: curMenu.icon, alt: 'list-icon', style: curMenu.iconStyle }))] })) }), "".concat(curMenu.value, "-").concat(idx)));
        }) })));
});
ListFormGroupType.defaultProps = {
    fontStyle: undefined,
    backgroundColor: undefined,
    t: undefined,
};

export { ListFormGroupType as default };
//# sourceMappingURL=ListFormGroupType.js.map
