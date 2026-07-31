import { Story } from '@storybook/react';
import Modal from './Modal';
import { ModalArgs } from './types';
declare const _default: {
    title: string;
    component: typeof Modal;
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
export declare const DefaultModal: Story<ModalArgs>;
