import { Story } from '@storybook/react';
import Badge from './Badge';
import { BadgeArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Badge;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        label: {
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
        leftIconVisible: {
            control: {
                type: string;
            };
        };
        rightIconVisible: {
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimaryBadge: Story<BadgeArgs>;
