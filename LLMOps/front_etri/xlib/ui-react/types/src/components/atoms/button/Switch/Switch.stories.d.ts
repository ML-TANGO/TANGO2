import { Story } from '@storybook/react';
import Switch from './Switch';
import { SwitchArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Switch;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        size: {
            options: string[];
            control: {
                type: string;
            };
        };
        disabled: {
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
        labelAlign: {
            options: string[];
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimarySwitch: Story<SwitchArgs>;
