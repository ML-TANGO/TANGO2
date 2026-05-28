import { Story } from '@storybook/react';
import Table from './Table';
import { TableArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Table;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        pagingBtnAlign: {
            option: string[];
            control: {
                type: string;
            };
        };
        PagingBtn: {
            control: {
                disable: boolean;
            };
        };
    };
};
export default _default;
export declare const BasicTable: Story<TableArgs>;
