/// <reference types="react" />
import i18n from 'react-i18next';
import { Properties as CSSProperties } from 'csstype';
import { ListType } from '../types';
declare type Props = {
    type: string;
    list: ListType[];
    selectedIdx: number;
    fontStyle?: CSSProperties;
    theme: ThemeType;
    backgroundColor?: string;
    onSelect: (idx: number, e: React.MouseEvent) => void;
    onListController: (e: React.KeyboardEvent<HTMLUListElement>, selectboxType: string) => void;
    t?: i18n.TFunction<'translation'>;
};
declare const ListFormGroupType: import("react").ForwardRefExoticComponent<Props & import("react").RefAttributes<HTMLUListElement>>;
export default ListFormGroupType;
