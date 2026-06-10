import { __read, __spreadArray, __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { useTrie as S } from '../../../../packages/react-utils/pack/index.js';
import downIcon from '../../../static/images/icons/ic-down.svg.js';
import { arrayToString, isSameArray, theme } from '../../../utils/utils.js';
import classNames from '../../../../modules/classnames/bind.js';
import { useRef, useMemo, useState, useCallback, useEffect, useLayoutEffect } from 'react';
import ListFormDefaultType from './ListForm/ListFormDefaultType.js';
import ListFormGroupType from './ListForm/ListFormGroupType.js';
import ListFormSelectBoxType from './ListForm/ListFormSelectBoxType.js';
import style from './Selectbox.module.scss.js';
import CheckboxFormDefault from './SelectboxForm/CheckboxFormDefault.js';
import SelectFormDefaultType from './SelectboxForm/SelectFormDefaultType.js';
import SelectFormInputType from './SelectboxForm/SelectFormInputType.js';
import { SelectboxTypes, SelectboxStatus, SelectboxSize } from './types.js';

var cx = classNames.bind(style);
function Selectbox(_a) {
    var _b, _c, _d, _e, _f;
    var _g = _a.type, type = _g === void 0 ? SelectboxTypes.PRIMARY : _g, _h = _a.status, status = _h === void 0 ? SelectboxStatus.DEFAULT : _h, _j = _a.size, size = _j === void 0 ? SelectboxSize.MEDIUM : _j, _k = _a.isReadOnly, isReadOnly = _k === void 0 ? false : _k, _l = _a.isDisable, isDisable = _l === void 0 ? false : _l, _m = _a.isShowStatusCheck, isShowStatusCheck = _m === void 0 ? false : _m, _o = _a.list, list = _o === void 0 ? [] : _o, selectedItem = _a.selectedItem, selectedItemIdx = _a.selectedItemIdx, _p = _a.theme, theme$1 = _p === void 0 ? theme.PRIMARY_THEME : _p, _q = _a.labelIcon, labelIcon = _q === void 0 ? downIcon : _q, _r = _a.placeholder, placeholder = _r === void 0 ? '' : _r, fixedList = _a.fixedList, customStyle = _a.customStyle, initState = _a.initState, onChange = _a.onChange, t = _a.t, scrollAutoFocus = _a.scrollAutoFocus, onChangeCheckbox = _a.onChangeCheckbox, checkedList = _a.checkedList, checkboxMultiLang = _a.checkboxMultiLang, newSelectedItem = _a.newSelectedItem, _s = _a.newSelectedItemF, newSelectedItemF = _s === void 0 ? false : _s;
    // References
    var selectboxRef = useRef(null);
    var inputSelectboxRef = useRef(null);
    var listRef = useRef(null);
    var listDivRef = useRef(null);
    var isNotSelectedItem = useMemo(function () {
        if (selectedItemIdx !== undefined)
            return false;
        if (selectedItem !== undefined)
            return false;
        return true;
    }, [selectedItem, selectedItemIdx]);
    var _t = __read(useState(false), 2), mount = _t[0], setMount = _t[1];
    var _u = __read(useState(__spreadArray([], __read(list), false)), 2), selectboxList = _u[0], setSelectboxList = _u[1];
    var _v = __read(useState(false), 2), isOpen = _v[0], setIsOpen = _v[1];
    var _w = __read(useState(-1), 2), selectedIdx = _w[0], setSelectedIdx = _w[1];
    var _x = __read(useState(-1), 2), prevSelectedIdx = _x[0], setPrevSelectedIdx = _x[1];
    var _y = __read(useState(false), 2), checkVisible = _y[0], setCheckVisible = _y[1];
    // 이전 상태의 list와 다음 상태의 list의 비교를 위한 state
    var _z = __read(useState(list), 2), prevArray = _z[0], setPrevArray = _z[1];
    // input 타입 selectbox state
    // input box에 표현될 string
    var _0 = __read(useState(''), 2), inputedValue = _0[0], setInputedValue = _0[1];
    // group 타입 selectbox staate
    // group타입 selectbox일 경우 원소가 isTitle이 아닌 index 단위가 가장 작은 index (리스트 포커싱 로직 계산)
    var _1 = __read(useState(-1), 2), groupTypeFirstIdx = _1[0], setGroupTypeFirstIdx = _1[1];
    // group Type 선택된 list
    var _2 = __read(useState([]), 2), checkboxList = _2[0], setCheckboxList = _2[1];
    // list의 index memoization
    var idxMemo = useMemo(function () {
        var dictionary = {};
        if (Array.isArray(list)) {
            list.forEach(function (l, idx) {
                var _a;
                // list의 value에 대한 정보 저장
                dictionary = __assign(__assign({}, dictionary), (_a = {}, _a[String(l.value)] = idx, _a));
            });
        }
        return dictionary;
    }, [list]);
    // trie 객체
    var trie = S((function () {
        if (Array.isArray(list)) {
            var trieForm = list.map(function (data) {
                var options = {};
                Object.keys(data).forEach(function (d) {
                    var _a;
                    if (d !== 'value' && d !== 'label') {
                        options = __assign(__assign({}, options), (_a = {}, _a[d] = data[d], _a));
                    }
                });
                return {
                    key: data.value,
                    label: arrayToString(data.label, t),
                    options: options,
                };
            });
            return trieForm;
        }
        return [];
    })(), type === SelectboxTypes.SEARCH);
    /**
     * list toggle
     */
    var onToggle = function () {
        if (!isReadOnly && !isDisable) {
            setIsOpen(function (isOpen) { return !isOpen; });
        }
        else {
            setIsOpen(false);
        }
    };
    /**
     * 선택된 list의 요소와 list요소의 index, event를 외부로 전달
     * @param idx
     * @param e
     */
    var dataDelivery = function (listItem, idx, e) {
        if (onChange)
            onChange(listItem, idx, e);
    };
    var onInputBlur = useCallback(function () {
        if (!isDisable && list.length > 0) {
            // setSelectboxList(_.cloneDeep(list));
            setSelectboxList(__spreadArray([], __read(list), false));
            if (newSelectedItem)
                return;
            if (prevSelectedIdx < 0) {
                setInputedValue('');
                setSelectedIdx(-1);
            }
            else {
                setInputedValue(arrayToString(list[prevSelectedIdx].label, t));
                setSelectedIdx(prevSelectedIdx);
            }
        }
    }, [isDisable, list, prevSelectedIdx, t, newSelectedItem]);
    var onSelectboxBlur = useCallback(function () {
        if (!isDisable && list.length > 0) {
            if (prevSelectedIdx >= 0) {
                setSelectedIdx(prevSelectedIdx);
            }
        }
    }, [isDisable, list.length, prevSelectedIdx]);
    /**
     * input type selectbox onChange
     * @param e
     */
    var onInputChange = function (e) {
        if (!isOpen)
            setIsOpen(true);
        var inputed = String(e.target.value);
        setInputedValue(inputed);
        if (inputed === '') {
            // setSelectboxList(_.cloneDeep(list));
            setSelectboxList(__spreadArray([], __read(list), false));
            return;
        }
        // 입력된 문자열로 시작하는 데이터를 trie에서 찾기
        var value = trie.containList(inputed);
        var newList = value.map(function (listData) {
            var label = listData.label, key = listData.key, options = listData.options;
            var nList = __assign(__assign({}, options), { label: label, value: key });
            return nList;
        });
        setSelectboxList(newList);
        setSelectedIdx(0);
    };
    /**
     * 리스트에서 특정 원소 선택
     * @param idx
     * @param e
     */
    var onSelect = function (idx, e) {
        e.stopPropagation();
        for (var i = 0; i < list.length; i++) {
            if (list[i].value === selectboxList[idx].value) {
                setPrevSelectedIdx(i);
                break;
            }
        }
        setSelectedIdx(idx);
        dataDelivery(selectboxList[idx], idxMemo[String(selectboxList[idx].value)], e);
        if (type === SelectboxTypes.SEARCH) {
            setInputedValue(arrayToString(selectboxList[idx].label, t));
        }
        setIsOpen(false);
    };
    var onSelectCheckbox = useCallback(function (curMenu) {
        var selectedList = checkboxList === null || checkboxList === void 0 ? void 0 : checkboxList.filter(function (data) {
            if (data.name)
                return data.name === curMenu.name;
            return data.label === curMenu.label;
        });
        if ((checkboxList === null || checkboxList === void 0 ? void 0 : checkboxList.indexOf(selectedList[0])) !== -1) {
            // const deepBoxList = _.cloneDeep(checkboxList);
            var deepBoxList = __spreadArray([], __read(checkboxList), false);
            if (checkboxList)
                deepBoxList === null || deepBoxList === void 0 ? void 0 : deepBoxList.splice(checkboxList.indexOf(selectedList[0]), 1);
            setCheckboxList(deepBoxList);
            if (onChangeCheckbox)
                onChangeCheckbox(deepBoxList);
        }
        else {
            setCheckboxList(function (prev) { return __spreadArray(__spreadArray([], __read(prev), false), [curMenu], false); });
            if (onChangeCheckbox)
                onChangeCheckbox(__spreadArray(__spreadArray([], __read(checkboxList), false), [curMenu], false));
        }
    }, [checkboxList, onChangeCheckbox]);
    /**
     * 선택된 항목의 index 설정
     * @param idx index
     */
    var onSetSelectedIdx = useCallback(function (idx) {
        setSelectedIdx(idx);
        // setPrevSelectedIdx(idx);
        if (type === SelectboxTypes.SEARCH) {
            setInputedValue(arrayToString(selectboxList[idx].label, t));
        }
    }, [selectboxList, t, type]);
    /**
     * list keyboard controll
     * @param e
     */
    var onListController = function (e, selectboxType) {
        if (e.key === 'Escape' && isOpen === true) {
            setIsOpen(false);
            if (type === SelectboxTypes.SEARCH)
                onInputBlur();
            else
                onSelectboxBlur();
            return;
        }
        // base case => list의 길이가 0이면 종료
        if (selectboxList.length === 0)
            return;
        var idx = 0;
        var isSet = false;
        if (e.key === 'ArrowDown') {
            // 아래로 내리기
            setIsOpen(true);
            if (selectboxType === SelectboxTypes.GROUP) {
                if (groupTypeFirstIdx === -1)
                    return;
                // group type 리스트에 대한 list index 설정
                var count = 0;
                idx = selectedIdx;
                while (count < selectboxList.length) {
                    if (idx + 1 < selectboxList.length) {
                        idx += 1;
                    }
                    else {
                        idx = 0;
                    }
                    if (!selectboxList[idx].isTitle) {
                        break;
                    }
                    count++;
                }
            }
            else {
                var count = 0;
                idx = selectedIdx;
                while (count < selectboxList.length) {
                    if (idx + 1 < selectboxList.length) {
                        idx += 1;
                    }
                    else {
                        idx = 0;
                    }
                    if (!selectboxList[idx].isDisable) {
                        break;
                    }
                    count++;
                }
            }
            onSetSelectedIdx(idx);
            e.preventDefault(); // 커서 위치이동 방지
        }
        else if (e.key === 'ArrowUp') {
            // 위로 올리기
            setIsOpen(true);
            if (selectboxType === SelectboxTypes.GROUP) {
                if (groupTypeFirstIdx === -1)
                    return;
                // group type 리스트에 대한 list index 설정
                var count = 0;
                idx = selectedIdx;
                while (count < selectboxList.length) {
                    if (idx - 1 > 0) {
                        idx -= 1;
                    }
                    else if (idx === groupTypeFirstIdx) {
                        idx = selectboxList.length - 1;
                    }
                    if (!selectboxList[idx].isTitle) {
                        break;
                    }
                    count++;
                }
            }
            else {
                // group type 리스트에 대한 list index 설정
                var count = 0;
                var roundCnt = 0;
                idx = selectedIdx;
                while (count < selectboxList.length) {
                    idx--;
                    count++;
                    roundCnt++;
                    if (count < 0) {
                        count = selectboxList.length - 1;
                    }
                    if (idx === -1) {
                        idx = selectboxList.length - 1;
                    }
                    if (!selectboxList[idx].isDisable) {
                        isSet = true;
                        break;
                    }
                    if (roundCnt === selectboxList.length - 1) {
                        break;
                    }
                }
            }
            if (isSet) {
                onSetSelectedIdx(idx);
            }
            e.preventDefault(); // 커서 위치이동 방지
        }
        else if (e.key === 'Enter' && isOpen === true) {
            if (!selectboxList[selectedIdx].isDisable) {
                for (var i = 0; i < list.length; i++) {
                    if (list[i].value === selectboxList[selectedIdx].value) {
                        setPrevSelectedIdx(i);
                        break;
                    }
                }
                dataDelivery(selectboxList[selectedIdx], idxMemo[String(selectboxList[selectedIdx].value)], e);
                if (type === SelectboxTypes.SEARCH) {
                    setInputedValue(arrayToString(selectboxList[selectedIdx].label));
                }
                setIsOpen(false);
            }
        }
    };
    /**
     * 다른 영역 클릭
     */
    var onDiffAreaClick = useCallback(function (e) {
        var _a, _b, _c;
        if (!((_a = selectboxRef.current) === null || _a === void 0 ? void 0 : _a.contains(e.target)) &&
            !((_b = listRef.current) === null || _b === void 0 ? void 0 : _b.contains(e.target)) &&
            !((_c = inputSelectboxRef.current) === null || _c === void 0 ? void 0 : _c.contains(e.target))) {
            setIsOpen(false);
            if (type === SelectboxTypes.SEARCH) {
                onInputBlur();
            }
            else {
                onSelectboxBlur();
            }
        }
    }, [onInputBlur, onSelectboxBlur, type]);
    /**
     * 컴포넌트 mount 시
     * 리스트의 선택된 요소 state에 설정
     */
    var initSelectedValueSetting = useCallback(function () {
        if (selectedItemIdx !== undefined &&
            selectedItemIdx >= 0 &&
            selectedItemIdx < selectboxList.length) {
            // selectedItemIdx를 우선순위로 리스트 계산
            if (selectboxList[selectedItemIdx].isTitle) {
                // 선택된 index가 타이틀일 경우(그룹타입) 선택되지 않도록 수정
                onSetSelectedIdx(-1);
            }
            else {
                onSetSelectedIdx(selectedItemIdx);
                setPrevSelectedIdx(selectedItemIdx);
            }
        }
        else if (selectedItem) {
            // selectedItemIdx가 없고 selectedItem이 있을 경우 계산
            for (var i = 0; i < selectboxList.length; i++) {
                if (selectboxList[i].value === selectedItem.value) {
                    if (selectboxList[i].isTitle) {
                        onSetSelectedIdx(-1);
                    }
                    else {
                        onSetSelectedIdx(i);
                        setPrevSelectedIdx(i);
                    }
                    break;
                }
            }
        }
        else if (initState) {
            setInputedValue('');
            setPrevSelectedIdx(-1);
            setSelectedIdx(-1);
        }
        // Group 타입일 경우 리스트에서 title이 아닌 첫번째 원소의 index설정
        if (type === SelectboxTypes.GROUP) {
            for (var i = 0; i < selectboxList.length; i++) {
                if (!selectboxList[i].isTitle) {
                    setGroupTypeFirstIdx(i);
                    break;
                }
            }
        }
        return undefined;
    }, [
        initState,
        onSetSelectedIdx,
        selectboxList,
        selectedItem,
        selectedItemIdx,
        type,
    ]);
    var scrollObserver = function (flag) {
        var _a;
        if (!flag)
            (_a = listDivRef === null || listDivRef === void 0 ? void 0 : listDivRef.current) === null || _a === void 0 ? void 0 : _a.scrollIntoView({
                block: 'end',
                inline: 'nearest',
            });
    };
    /**
     * 영역 클릭 이벤트 등록
     */
    useEffect(function () {
        if (type !== SelectboxTypes.CHECKBOX)
            document.addEventListener('click', onDiffAreaClick);
        return function () {
            document.removeEventListener('click', onDiffAreaClick);
        };
    }, [onDiffAreaClick, type]);
    /**
     * list scroll 이벤트
     */
    useEffect(function () {
        var list = listRef.current;
        if (isOpen &&
            list &&
            selectedIdx >= 0 &&
            list.childNodes.length > selectedIdx) {
            var element = list.childNodes[selectedIdx];
            var scrollPos = element.offsetTop - 14;
            if (type === SelectboxTypes.GROUP &&
                selectedIdx === 1 &&
                selectboxList[selectedIdx - 1].isTitle) {
                list.scrollTo({
                    top: scrollPos -
                        16 -
                        list.childNodes[selectedIdx - 1].offsetTop,
                    behavior: 'smooth',
                });
                return;
            }
            list.scrollTo({ top: scrollPos, behavior: 'smooth' });
        }
    }, [isOpen, selectboxList, selectedIdx, type]);
    useEffect(function () {
        if (isShowStatusCheck) {
            if (isOpen) {
                setCheckVisible(false);
            }
            else {
                setCheckVisible(true);
            }
        }
    }, [isOpen, isShowStatusCheck]);
    /**
     * list 변경 관찰 -> flag 수정하여 list 업데이트
     */
    useLayoutEffect(function () {
        if (mount && !isSameArray(prevArray, list)) {
            setPrevArray(list);
            // setSelectboxList(_.cloneDeep(list));
            setSelectboxList(__spreadArray([], __read(list), false));
            setMount(false);
        }
    }, [list, mount, prevArray]);
    useEffect(function () {
        setSelectboxList(__spreadArray([], __read(list), false));
        var newList = list.filter(function (li) {
            return checkedList === null || checkedList === void 0 ? void 0 : checkedList.includes(li.value);
        });
        setCheckboxList(newList);
    }, [checkedList, list]);
    useEffect(function () {
        if (fixedList) {
            var handleListPos = function () {
                if (!isOpen)
                    return;
                var selectbox = selectboxRef.current;
                var list = listRef.current;
                if (selectbox && list) {
                    var bBox = selectbox.getBoundingClientRect();
                    list.style.width = "".concat(bBox.width, "px");
                    list.style.position = 'fixed';
                    list.style.top = "".concat(bBox.y + bBox.height + 4, "px");
                    list.style.left = "".concat(bBox.x, "px");
                }
            };
            handleListPos();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, selectboxRef.current, listRef.current, fixedList]);
    useLayoutEffect(function () {
        if (initState) {
            setMount(false);
        }
    }, [initState]);
    /**
     * 컴포넌트가 마운트 되었을 경우 한번만 실행
     * 선택된 원소가 없거나 리스트가 업데이트 될 경우
     * 컴포넌트 업데이트가 필요하므로 mount flag 변경
     */
    useLayoutEffect(function () {
        if (!mount) {
            if (!isNotSelectedItem) {
                setMount(true);
            }
            initSelectedValueSetting();
        }
    }, [initSelectedValueSetting, isNotSelectedItem, mount]);
    useEffect(function () {
        if (newSelectedItemF) {
            if (newSelectedItem) {
                for (var i = 0; i < selectboxList.length; i++) {
                    if (selectboxList[i].value === newSelectedItem.value) {
                        setSelectedIdx(i);
                        setInputedValue(newSelectedItem.label);
                    }
                }
            }
            else {
                setSelectedIdx(-1);
                setInputedValue('');
                setPrevSelectedIdx(-1);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [newSelectedItem, newSelectedItemF]);
    return (jsxs("div", __assign({ className: cx('jp', 'selectbox'), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.globalForm }, { children: [(type === SelectboxTypes.PRIMARY ||
                type === SelectboxTypes.GROUP ||
                type === SelectboxTypes.MULTI) && (jsx("div", __assign({ className: cx(size, 'default-selectbox'), onClick: onToggle, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.selectboxForm }, { children: jsx(SelectFormDefaultType, { type: type, ref: selectboxRef, theme: theme$1, status: status, isOpen: isOpen, selectedItem: 
                    // selectedIdx >= 0 ? arrayToString(list[selectedIdx].label, t) : ''
                    selectedIdx >= 0 ? list[selectedIdx] : null, placeholder: t ? t(placeholder || '') : placeholder, labelIcon: labelIcon, isReadonly: isReadOnly, isDisable: isDisable, fontStyle: (_b = customStyle === null || customStyle === void 0 ? void 0 : customStyle.fontStyle) === null || _b === void 0 ? void 0 : _b.selectbox, backgroundColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.color, onListController: onListController, t: t }) }))), type === SelectboxTypes.SEARCH && (jsx("div", __assign({ className: cx(size, 'input-selectbox'), onClick: onToggle, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.selectboxForm }, { children: jsx(SelectFormInputType, { type: type, ref: inputSelectboxRef, status: status, isOpen: isOpen, inputedValue: inputedValue, labelIcon: labelIcon, isReadonly: isReadOnly, isDisable: isDisable, checkVisible: checkVisible, placeholder: placeholder, fontStyle: (_c = customStyle === null || customStyle === void 0 ? void 0 : customStyle.fontStyle) === null || _c === void 0 ? void 0 : _c.selectbox, onListController: onListController, onInputChange: onInputChange, t: t }) }))), type === SelectboxTypes.CHECKBOX && (jsx("div", __assign({ className: cx(size, 'default-selectbox'), onClick: onToggle, style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.selectboxForm }, { children: jsx(CheckboxFormDefault, { type: type, ref: selectboxRef, theme: theme$1, status: status, isOpen: isOpen, placeholder: t ? t(placeholder || '') : placeholder, labelIcon: labelIcon, isReadonly: isReadOnly, isDisable: isDisable, fontStyle: (_d = customStyle === null || customStyle === void 0 ? void 0 : customStyle.fontStyle) === null || _d === void 0 ? void 0 : _d.selectbox, backgroundColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.color, onListController: onListController, t: t, label: '\uCEEC\uB7FC\uC774\uB984', checkboxList: checkboxList, checkboxMultiLang: checkboxMultiLang }) }))), isOpen && selectboxList.length > 0 && (jsxs("div", __assign({ className: cx(size, 'list'), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.listForm }, { children: [(type === SelectboxTypes.PRIMARY ||
                        type === SelectboxTypes.SEARCH) && (jsx("div", __assign({ className: cx('list-default'), ref: scrollAutoFocus ? listDivRef : undefined }, { children: jsx(ListFormDefaultType, { ref: listRef, selectedIdx: selectedIdx, type: type, theme: theme$1, list: selectboxList, fontStyle: (_e = customStyle === null || customStyle === void 0 ? void 0 : customStyle.fontStyle) === null || _e === void 0 ? void 0 : _e.list, onSelect: onSelect, onListController: onListController, scrollObserver: scrollObserver, backgroundColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.color, t: t }) }))), type === SelectboxTypes.GROUP && (jsx("div", __assign({ className: cx('list-group') }, { children: jsx(ListFormGroupType, { type: type, ref: listRef, list: selectboxList, selectedIdx: selectedIdx, theme: theme$1, fontStyle: (_f = customStyle === null || customStyle === void 0 ? void 0 : customStyle.fontStyle) === null || _f === void 0 ? void 0 : _f.list, backgroundColor: customStyle === null || customStyle === void 0 ? void 0 : customStyle.color, onSelect: onSelect, onListController: onListController, t: t }) }))), type === SelectboxTypes.CHECKBOX && (jsx("div", __assign({ className: cx('list-default') }, { children: jsx(ListFormSelectBoxType, { ref: listRef, list: selectboxList, onDiffAreaClick: onDiffAreaClick, onSelectCheckbox: onSelectCheckbox, checkedList: checkedList }) })))] })))] })));
}
Selectbox.defaultProps = {
    type: SelectboxTypes.PRIMARY,
    status: SelectboxStatus.DEFAULT,
    size: SelectboxSize.MEDIUM,
    labelIcon: downIcon,
    list: [],
    selectedItem: undefined,
    selectedItemIdx: undefined,
    isReadOnly: false,
    isDisable: false,
    isShowStatusCheck: false,
    placeholder: '',
    customStyle: undefined,
    onChange: undefined,
    onChangeCheckbox: undefined,
    fixedList: false,
    t: undefined,
    scrollAutoFocus: undefined,
    theme: theme.PRIMARY_THEME,
    checkedList: undefined,
    checkboxMultiLang: '',
    initState: false,
    newSelectedItem: undefined,
    newSelectedItemF: false,
};

export { Selectbox as default };
//# sourceMappingURL=Selectbox.js.map
