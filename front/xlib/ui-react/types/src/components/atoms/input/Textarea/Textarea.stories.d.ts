import { Story } from '@storybook/react';
import { TextareaArgs } from './types';
declare const _default: {
    title: string;
    component: {
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
        theme: {
            options: ("jp-primary" | "jp-dark")[];
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
        placeholder: {
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
export declare const TextareaPrimary: Story<TextareaArgs>;
