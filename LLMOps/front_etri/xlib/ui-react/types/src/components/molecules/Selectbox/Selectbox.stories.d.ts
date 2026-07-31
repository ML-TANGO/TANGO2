import { Story } from '@storybook/react';
import Selectbox from './Selectbox';
import { SelectboxArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Selectbox;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        status: {
            options: string[];
            control: {
                type: string;
            };
        };
        type: {
            options: string[];
            control: {
                disable: boolean;
            };
        };
        theme: {
            options: string[];
            control: {
                type: string;
            };
        };
        size: {
            options: string[];
            control: {
                type: string;
            };
        };
        isReadOnly: {
            control: {
                type: string;
            };
        };
        selectedItemIdx: {
            control: {
                disable: boolean;
            };
        };
        onClick: {
            action: string;
        };
        onChange: {
            action: string;
        };
    };
};
export default _default;
export declare const PrimarySelecbox: Story<SelectboxArgs>;
export declare const GroupSelectbox: Story<any>;
export declare const SearchSelectbox: Story<SelectboxArgs>;
export declare const checkboxSelectbox: Story<SelectboxArgs>;
