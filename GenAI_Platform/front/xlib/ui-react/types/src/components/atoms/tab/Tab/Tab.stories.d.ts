import { Story } from '@storybook/react';
import Tab from './Tab';
import { TabArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Tab;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        onClick: {
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
export declare const PrimaryTab: Story<TabArgs>;
