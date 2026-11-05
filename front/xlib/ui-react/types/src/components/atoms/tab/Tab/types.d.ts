/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
interface CategoryType {
    label: string;
    component?: (props: {
        [key: string]: any;
    }) => JSX.Element;
    renderComponentProps?: {
        [key: string]: any;
    };
}
interface TabArgs {
    category?: CategoryType[];
    selectedItem?: number;
    theme: ThemeType;
    customStyle?: {
        tab?: CSSProperties;
        btnArea?: CSSProperties;
        selectBtnArea?: CSSProperties;
        label?: CSSProperties;
        line?: CSSProperties;
        component?: CSSProperties;
    };
    readonly onClick?: (e?: React.MouseEvent<HTMLLIElement>) => void;
}
export { CategoryType, TabArgs };
