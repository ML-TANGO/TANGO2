import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { forwardRef, useRef } from 'react';
import checkIconGray from '../../../../static/images/icons/00-ic-basic-check-gray.svg.js';
import checkIconBlue from '../../../../static/images/icons/00-ic-basic-check-blue.svg.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';

var cx = classNames.bind(style);
var SelectFormInputType = forwardRef(function (_a, ref) {
    var type = _a.type, status = _a.status, inputedValue = _a.inputedValue, isOpen = _a.isOpen, labelIcon = _a.labelIcon, placeholder = _a.placeholder, isReadonly = _a.isReadonly, isDisable = _a.isDisable, checkVisible = _a.checkVisible, fontStyle = _a.fontStyle, backgroundColor = _a.backgroundColor, onListController = _a.onListController, onInputChange = _a.onInputChange, t = _a.t;
    var inputRef = useRef(null);
    var onClick = function () {
        var input = inputRef.current;
        if (input) {
            input.focus();
        }
    };
    return (jsxs("div", __assign({ className: cx('controller', status, isOpen && 'open', isReadonly && 'readonly', isDisable && 'disabled', checkVisible && 'check-box-div'), ref: ref, style: {
            backgroundColor: backgroundColor,
        }, onClick: onClick }, { children: [checkVisible && (jsx("img", { className: cx('input-check-icon'), src: status !== 'error' && inputedValue && inputedValue !== ''
                    ? checkIconBlue
                    : checkIconGray, alt: 'icon' })), jsx("input", { ref: inputRef, className: cx('input-box', checkVisible && 'check-box'), value: inputedValue, onChange: onInputChange, onKeyDown: function (e) {
                    onListController(e, type);
                }, placeholder: t ? t(placeholder) : placeholder, readOnly: isReadonly, disabled: isDisable, style: __assign(__assign({}, fontStyle), { backgroundColor: backgroundColor }) }), jsx("img", { src: labelIcon, alt: 'arrow-icon', className: cx('arrow-icon', isOpen && 'open') })] })));
});
SelectFormInputType.defaultProps = {
    fontStyle: undefined,
    t: undefined,
    backgroundColor: undefined,
};

export { SelectFormInputType as default };
//# sourceMappingURL=SelectFormInputType.js.map
