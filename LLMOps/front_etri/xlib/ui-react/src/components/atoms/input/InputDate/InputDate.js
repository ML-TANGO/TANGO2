import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { InputDateStatus, InputDateSize } from './types.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './InputDate.module.scss.js';

var cx = classNames.bind(style);
function InputDate(_a) {
    var status = _a.status, size = _a.size, placeholder = _a.placeholder, isReadOnly = _a.isReadOnly, disabled = _a.disabled, value = _a.value, max = _a.max, min = _a.min, name = _a.name, customSize = _a.customSize, onChange = _a.onChange;
    return (jsx("div", __assign({ className: cx('jp', 'input', 'input-date', isReadOnly && 'read-only', size, status === InputDateStatus.ERROR && 'error') }, { children: jsx("input", { type: 'date', min: min, max: max, name: name, placeholder: placeholder, value: value === undefined ? '' : value, disabled: disabled, readOnly: isReadOnly, style: customSize, onChange: onChange }) })));
}
InputDate.defaultProps = {
    value: '',
    status: InputDateStatus.DEFAULT,
    size: InputDateSize.MEDIUM,
    max: undefined,
    min: undefined,
    disabled: false,
    isReadOnly: false,
    placeholder: undefined,
    customSize: undefined,
    onChange: undefined,
    name: undefined,
};

export { InputDate as default };
//# sourceMappingURL=InputDate.js.map
