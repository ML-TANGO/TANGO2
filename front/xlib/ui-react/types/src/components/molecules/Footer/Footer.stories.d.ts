import { Story } from '@storybook/react';
import Footer, { FooterArgs } from './Footer';
declare const _default: {
    title: string;
    component: typeof Footer;
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
export declare const DefaultFooter: Story<FooterArgs>;
