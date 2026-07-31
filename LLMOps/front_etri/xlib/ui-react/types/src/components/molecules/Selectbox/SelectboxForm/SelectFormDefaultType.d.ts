/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
import { ListType } from '../types';
declare type Props = {
    type: string;
    status: string;
    isOpen: boolean;
    selectedItem: ListType | null;
    labelIcon: string;
    isReadonly: boolean;
    isDisable: boolean;
    theme: ThemeType;
    placeholder: string;
    backgroundColor?: string;
    fontStyle?: CSSProperties;
    placeholderStyle?: CSSProperties;
    onListController: (e: React.KeyboardEvent<HTMLDivElement>, selectboxType: string) => void;
    t?: i18n.TFunction<'translation'>;
};
declare const SelectFormDefaultType: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLDivElement>>;
export default SelectFormDefaultType;
