import { Story } from '@storybook/react';
import Spinner from './Spinner';
import { SpinnerArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Spinner;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        color: {
            options: string[];
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const PrimarySpinner: Story<SpinnerArgs>;
