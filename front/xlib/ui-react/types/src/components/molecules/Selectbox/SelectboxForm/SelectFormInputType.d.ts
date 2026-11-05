/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
declare type Props = {
    type: string;
    status: string;
    isOpen: boolean;
    inputedValue: string;
    labelIcon: string;
    placeholder: string;
    isReadonly: boolean;
    isDisable: boolean;
    checkVisible: boolean;
    fontStyle?: CSSProperties;
    backgroundColor?: string;
    onListController: (e: React.KeyboardEvent<HTMLInputElement>, type: string) => void;
    onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    t?: i18n.TFunction<'translation'>;
};
declare const SelectFormInputType: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLDivElement>>;
export default SelectFormInputType;
