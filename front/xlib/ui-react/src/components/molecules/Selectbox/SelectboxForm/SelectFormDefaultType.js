import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { forwardRef } from 'react';
import { arrayToString } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';

var cx = classNames.bind(style);
var SelectFormDefaultType = forwardRef(function (_a, ref) {
    var type = _a.type, status = _a.status, isOpen = _a.isOpen, selectedItem = _a.selectedItem, labelIcon = _a.labelIcon, isReadonly = _a.isReadonly, backgroundColor = _a.backgroundColor, isDisable = _a.isDisable, theme = _a.theme, placeholder = _a.placeholder, placeholderStyle = _a.placeholderStyle, fontStyle = _a.fontStyle, onListController = _a.onListController, t = _a.t;
    return (jsxs("div", __assign({ className: cx('controller', status, isOpen && 'open', theme, isReadonly && 'readonly', isDisable && 'disabled'), ref: ref, tabIndex: -1, onKeyDown: function (e) {
            onListController(e, type);
        }, style: {
            backgroundColor: backgroundColor,
        } }, { children: [selectedItem ? (jsxs("span", __assign({ style: fontStyle, className: cx(selectedItem === null || selectedItem === void 0 ? void 0 : selectedItem.iconAlign) }, { children: [(selectedItem === null || selectedItem === void 0 ? void 0 : selectedItem.icon) && (jsx("img", { className: cx('label-icon'), src: selectedItem.icon, alt: 'icon', style: selectedItem.iconStyle })), jsx("label", { children: arrayToString(selectedItem.label, t) })] }))) : (jsx("span", __assign({ style: placeholderStyle, className: cx('placeholder') }, { children: placeholder || '' }))), jsx("img", { src: labelIcon, alt: 'arrow-icon', className: cx('arrow-icon', isOpen && 'open') })] })));
});
SelectFormDefaultType.defaultProps = {
    fontStyle: undefined,
    placeholderStyle: undefined,
    backgroundColor: undefined,
    t: undefined,
};

export { SelectFormDefaultType as default };
//# sourceMappingURL=SelectFormDefaultType.js.map
