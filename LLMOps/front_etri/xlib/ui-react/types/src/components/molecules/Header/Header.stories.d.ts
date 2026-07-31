import { Story } from '@storybook/react';
import Header, { HeaderArgs } from './Header';
declare const _default: {
    title: string;
    component: typeof Header;
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
export declare const DefaultHeader: Story<HeaderArgs>;
