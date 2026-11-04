import { Story } from '@storybook/react';
import Tooltip from './Tooltip';
import { TooltipArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Tooltip;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        iconAlign: {
            options: string[];
            control: {
                type: string;
            };
        };
        horizontalAlign: {
            options: string[];
            control: {
                type: string;
            };
        };
        verticalAlign: {
            options: string[];
            control: {
                type: string;
            };
        };
        type: {
            options: string[];
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimaryTooltip: Story<TooltipArgs>;
