/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
import { CategoryType } from './types';
declare type Props = {
    category?: CategoryType[];
    selectedItem?: number;
    renderComponent?: any;
    renderComponentProps?: any;
    customStyle?: {
        tab?: CSSProperties;
        btnArea?: CSSProperties;
        selectBtnArea?: CSSProperties;
        label?: CSSProperties;
        line?: CSSProperties;
        component?: CSSProperties;
    };
    isScroll?: boolean;
    isScrollCorrection?: boolean;
    theme?: ThemeType;
    readonly onClick?: (idx: number, e?: React.MouseEvent<HTMLLIElement>) => void;
    readonly t?: i18n.TFunction<'translation'>;
};
declare function Tab({ category, selectedItem, renderComponent, renderComponentProps, customStyle, theme, isScroll, isScrollCorrection, onClick, t, }: Props): JSX.Element;
declare namespace Tab {
    var defaultProps: {
        category: never[];
        selectedItem: undefined;
        renderComponent: undefined;
        renderComponentProps: undefined;
        customStyle: {
            tabArea: {};
            selectBtnArea: {};
            label: {};
            line: {};
            component: {};
        };
        isScroll: boolean;
        isScrollCorrection: boolean;
        theme: "jp-primary";
        onClick: undefined;
        t: undefined;
    };
}
export default Tab;
