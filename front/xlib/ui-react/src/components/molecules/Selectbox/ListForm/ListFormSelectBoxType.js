import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import React, { useState, useCallback, useEffect } from 'react';
import classNames from '../../../../../modules/classnames/bind.js';
import style from '../Selectbox.module.scss.js';
import Checkbox from '../../../atoms/button/Checkbox/Checkbox.js';

classNames.bind(style);
var ListFormSelectBoxType = React.forwardRef(function (_a, ref) {
    var list = _a.list, onDiffAreaClick = _a.onDiffAreaClick, onSelectCheckbox = _a.onSelectCheckbox, checkedList = _a.checkedList;
    var _b = __read(useState(new Array(list.length).fill(false)), 2), checkedState = _b[0], setCheckedState = _b[1];
    var onChangeCheckBox = function (curMenu, position) {
        onSelectCheckbox(curMenu);
        var updatedCheckedState = checkedState.map(function (item, index) {
            return index === position ? !item : item;
        });
        setCheckedState(updatedCheckedState);
    };
    var changeStateHandler = useCallback(function () {
        var newCheckedState = checkedState.map(function (state, index) {
            if (checkedList === null || checkedList === void 0 ? void 0 : checkedList.includes(index)) {
                return !state;
            }
            return state;
        });
        setCheckedState(newCheckedState);
    }, [checkedList, checkedState]);
    useEffect(function () {
        document.addEventListener('click', onDiffAreaClick);
        return function () {
            document.removeEventListener('click', onDiffAreaClick);
        };
    }, [onDiffAreaClick]);
    useEffect(function () {
        if (checkedList) {
            changeStateHandler();
        }
    }, []);
    return (jsx("ul", __assign({ ref: ref, tabIndex: -1 }, { children: list.map(function (curMenu, idx) {
            return (jsx("div", __assign({ style: { display: 'flex', margin: '20px 10px' } }, { children: jsx(Checkbox, { label: curMenu.label, onChange: function () { return onChangeCheckBox(curMenu, idx); }, checked: checkedState[idx] }) }), curMenu.value));
        }) })));
});
ListFormSelectBoxType.defaultProps = {
    checkedList: undefined,
};

export { ListFormSelectBoxType as default };
//# sourceMappingURL=ListFormSelectBoxType.js.map
