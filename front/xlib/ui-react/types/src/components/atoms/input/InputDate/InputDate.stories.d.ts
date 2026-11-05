import { Story } from '@storybook/react';
import InputDate from './InputDate';
import { InputDateArgs } from './types';
declare const _default: {
    title: string;
    component: typeof InputDate;
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
    };
};
export default _default;
export declare const PrimaryInputNumber: Story<InputDateArgs>;
