import { Story } from '@storybook/react';
import InputText from './InputText';
import { InputTextArgs } from './types';
declare const _default: {
    title: string;
    component: typeof InputText;
    parameters: {
        componentSubtitle: string;
        layout: string;
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
        disableLeftIcon: {
            control: {
                type: string;
            };
        };
        disableRightIcon: {
            control: {
                type: string;
            };
        };
        disableClearBtn: {
            control: {
                type: string;
            };
        };
        value: {
            control: {
                disable: boolean;
            };
        };
        onChange: {
            action: string;
        };
        onClear: {
            action: string;
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
export declare const PrimaryInputText: Story<InputTextArgs>;
