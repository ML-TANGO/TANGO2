import React from 'react';
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
interface Props {
    type: string;
    status: string;
    isOpen: boolean;
    labelIcon: string;
    isReadonly: boolean;
    isDisable: boolean;
    theme: string;
    placeholder: string;
    backgroundColor?: string;
    fontStyle?: CSSProperties;
    placeholderStyle?: CSSProperties;
    onListController: (e: React.KeyboardEvent<HTMLDivElement>, selectboxType: string) => void;
    t?: i18n.TFunction<'translation'>;
    label: string;
    checkboxList: any;
    checkboxMultiLang?: string;
}
declare const CheckboxFormDefault: React.ForwardRefExoticComponent<Props & React.RefAttributes<HTMLDivElement>>;
export default CheckboxFormDefault;
