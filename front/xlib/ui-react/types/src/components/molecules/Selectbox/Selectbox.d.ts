import { Properties as CSSProperties } from 'csstype';
import i18n from 'react-i18next';
import { FontStyle, ListType, onChangeEventType } from './types';
declare type Props = {
    status?: string;
    type?: string;
    size?: string;
    labelIcon?: string;
    list?: Array<ListType>;
    placeholder?: string;
    selectedItem?: ListType | null;
    selectedItemIdx?: number;
    isReadOnly?: boolean;
    isDisable?: boolean;
    isShowStatusCheck?: boolean;
    theme?: ThemeType;
    customStyle?: {
        globalForm?: CSSProperties;
        selectboxForm?: CSSProperties;
        listForm?: CSSProperties;
        fontStyle?: {
            selectbox?: FontStyle;
            list?: FontStyle;
        };
        placeholderStyle?: CSSProperties;
        color?: string;
    };
    fixedList?: boolean;
    initState?: boolean;
    onChange?: (item: ListType, itemIdx: number, e?: onChangeEventType) => void;
    t?: i18n.TFunction<'translation'>;
    scrollAutoFocus?: boolean;
    onChangeCheckbox?: (curMenu: any) => void;
    checkedList?: number[];
    checkboxMultiLang?: string;
    newSelectedItem?: ListType;
    newSelectedItemF?: boolean;
};
declare function Selectbox({ type, status, size, isReadOnly, isDisable, isShowStatusCheck, list, selectedItem, selectedItemIdx, theme, labelIcon, placeholder, fixedList, customStyle, initState, onChange, t, scrollAutoFocus, onChangeCheckbox, checkedList, checkboxMultiLang, newSelectedItem, newSelectedItemF, }: Props): JSX.Element;
declare namespace Selectbox {
    var defaultProps: {
        type: string;
        status: string;
        size: string;
        labelIcon: string;
        list: never[];
        selectedItem: undefined;
        selectedItemIdx: undefined;
        isReadOnly: boolean;
        isDisable: boolean;
        isShowStatusCheck: boolean;
        placeholder: string;
        customStyle: undefined;
        onChange: undefined;
        onChangeCheckbox: undefined;
        fixedList: boolean;
        t: undefined;
        scrollAutoFocus: undefined;
        theme: "jp-primary";
        checkedList: undefined;
        checkboxMultiLang: string;
        initState: boolean;
        newSelectedItem: undefined;
        newSelectedItemF: boolean;
    };
}
export default Selectbox;
