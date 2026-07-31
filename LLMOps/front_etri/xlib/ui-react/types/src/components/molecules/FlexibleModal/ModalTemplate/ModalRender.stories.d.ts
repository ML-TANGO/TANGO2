import { Story } from '@storybook/react';
import ModalRender from './ModalRender/ModalRender';
declare const _default: {
    title: string;
    component: typeof ModalRender;
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
export declare const defaultRender: Story;
