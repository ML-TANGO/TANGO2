import { Story } from '@storybook/react';
import Radio from './Radio';
import { RadioArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Radio;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        onChange: {
            action: string;
        };
        selectedValue: {
            control: {
                type: string;
            };
        };
        isReadOnly: {
            control: {
                type: string;
            };
        };
        t: {
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
    };
};
export default _default;
export declare const PrimaryRadio: Story<RadioArgs>;
