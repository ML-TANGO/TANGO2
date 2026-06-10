import { Story } from '@storybook/react';
import Popup from './Popup';
import { PopupProps } from './type';
declare const _default: {
    title: string;
    component: typeof Popup;
    parameters: {
        componentSubtitle: string;
        layout: string;
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
export declare const PrimaryPopup: Story<PopupProps>;
