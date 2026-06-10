import { Story } from '@storybook/react';
import Button from './Button';
import { ButtonArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Button;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        type: {
            options: string[];
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
        size: {
            options: string[];
            control: {
                type: string;
            };
        };
        children: {
            control: {
                type: string;
            };
        };
        iconAlign: {
            options: string[];
            control: {
                type: string;
            };
        };
        loading: {
            control: {
                type: string;
            };
        };
        onClick: {
            action: string;
        };
        onMouseOver: {
            action: string;
        };
        onMouseLeave: {
            action: string;
        };
    };
};
export default _default;
export declare const Primary: Story<ButtonArgs>;
export declare const PrimaryReverse: Story<ButtonArgs>;
export declare const PrimaryLight: Story<ButtonArgs>;
export declare const Red: Story<ButtonArgs>;
export declare const RedReverse: Story<ButtonArgs>;
export declare const RedLight: Story<ButtonArgs>;
export declare const Secondary: Story<ButtonArgs>;
export declare const Gray: Story<ButtonArgs>;
export declare const TextUnderline: Story<ButtonArgs>;
export declare const NoneBorder: Story<ButtonArgs>;
export declare const LoadingButton: Story<ButtonArgs>;
export declare const Icon: Story<ButtonArgs>;
