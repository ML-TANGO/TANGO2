import { Story } from '@storybook/react';
import Emptybox from './Emptybox';
import { EmptyboxArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Emptybox;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        theme: {
            options: ("jp-primary" | "jp-dark")[];
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimaryEmptybox: Story<EmptyboxArgs>;
