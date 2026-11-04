import { Story } from '@storybook/react';
import InputNumber from './InputNumber';
import { InputNumberArgs } from './types';
declare const _default: {
    title: string;
    component: typeof InputNumber;
    parameter: {
        componentSubtitle: string;
    };
    argTypes: {
        status: {
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
        placeholder: {
            control: {
                type: string;
            };
        };
        disabled: {
            control: {
                type: string;
            };
        };
        isReadOnly: {
            control: {
                type: string;
            };
        };
        onChange: {
            action: string;
        };
        value: {
            control: {
                disable: boolean;
            };
        };
        theme: {
            options: ("jp-primary" | "jp-dark")[];
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimaryInputNumber: Story<InputNumberArgs>;
