import { Story } from '@storybook/react';
import Checkbox from './Checkbox';
import { CheckboxArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Checkbox;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        disabled: {
            control: {
                type: string;
            };
        };
        label: {
            control: {
                type: string;
            };
        };
        onChange: {
            action: string;
        };
        checked: {
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
export declare const PrimaryCheckbox: Story<CheckboxArgs>;
