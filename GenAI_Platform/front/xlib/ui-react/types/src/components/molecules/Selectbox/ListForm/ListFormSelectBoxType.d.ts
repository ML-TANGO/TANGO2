import React from 'react';
import { ListType } from '../types';
interface Props {
    list: ListType[];
    onDiffAreaClick: (e: MouseEvent) => void;
    onSelectCheckbox: (curMenu: ListType) => void;
    checkedList?: number[];
}
declare const ListFormSelectBoxType: React.ForwardRefExoticComponent<Props & React.RefAttributes<HTMLUListElement>>;
export default ListFormSelectBoxType;
