import { Story } from '@storybook/react';
import InputPassword from './InputPassword';
import { InputPasswordArgs } from './types';
declare const _default: {
    title: string;
    component: typeof InputPassword;
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
        size: {
            options: string[];
            control: {
                type: string;
            };
        };
        isDisabled: {
            control: {
                type: string;
            };
        };
        isReadOnly: {
            control: {
                type: string;
            };
        };
        disableShowBtn: {
            control: {
                type: string;
            };
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
        onChange: {
            action: string;
        };
    };
};
export default _default;
export declare const PrimaryInputPassword: Story<InputPasswordArgs>;
