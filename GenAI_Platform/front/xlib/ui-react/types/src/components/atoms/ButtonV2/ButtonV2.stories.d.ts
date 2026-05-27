import { Story } from '@storybook/react';
import ButtonV2 from './ButtonV2';
import { ButtonV2Props } from './type';
declare const _default: {
    title: string;
    component: typeof ButtonV2;
    parameters: {
        componentSubtitle: string;
        layout: string;
    };
    argTypes: {
        control: {
            type: string;
        };
    };
};
export default _default;
export declare const PrimaryPopup: Story<ButtonV2Props>;
