import { Story } from '@storybook/react';
import Loading from './Loading';
import { LoadingArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Loading;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {};
};
export default _default;
export declare const PrimaryLoading: Story<LoadingArgs>;
export declare const CircleLoading: Story<LoadingArgs>;
