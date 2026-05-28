import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import React, { useState, useEffect } from 'react';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';

var cx = classNames.bind(style);
var CheckboxFormDefault = React.forwardRef(function (_a, ref) {
    var type = _a.type, status = _a.status, isOpen = _a.isOpen, labelIcon = _a.labelIcon, isReadonly = _a.isReadonly, backgroundColor = _a.backgroundColor, isDisable = _a.isDisable, theme = _a.theme, placeholder = _a.placeholder, placeholderStyle = _a.placeholderStyle; _a.fontStyle; var onListController = _a.onListController; _a.t; _a.label; var checkboxList = _a.checkboxList, checkboxMultiLang = _a.checkboxMultiLang;
    var _b = __read(useState([]), 2), list = _b[0], setList = _b[1];
    useEffect(function () {
        setList(Array.from(checkboxList));
    }, [checkboxList]);
    return (jsxs("div", __assign({ className: cx('controller', status, theme, isReadonly && 'readonly', isDisable && 'disabled'), ref: ref, tabIndex: -1, onKeyDown: function (e) {
            onListController(e, type);
        }, style: {
            backgroundColor: backgroundColor,
        } }, { children: [list.length > 0 ? (jsxs("span", { children: [list[0].name ? list[0].name : list[0].label, list.length > 1 && " ".concat(checkboxMultiLang, " ").concat(list.length - 1)] })) : (jsx("span", __assign({ style: placeholderStyle, className: cx('placeholder') }, { children: placeholder || '' }))), jsx("img", { src: labelIcon, alt: 'arrow-icon', className: cx('arrow-icon', isOpen && 'open') })] })));
});
CheckboxFormDefault.defaultProps = {
    fontStyle: undefined,
    placeholderStyle: undefined,
    backgroundColor: undefined,
    t: undefined,
    checkboxMultiLang: undefined,
};

export { CheckboxFormDefault as default };
//# sourceMappingURL=CheckboxFormDefault.js.map
