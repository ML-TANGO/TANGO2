import { Story } from '@storybook/react';
import SideNav, { SideNavArgs } from './SideNav';
declare const _default: {
    title: string;
    component: typeof SideNav;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        responsive: {
            control: {
                type: string;
            };
        };
        theme: {
            options: string[];
            control: {
                type: string;
            };
        };
        width: {
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const DefaultSideNav: Story<SideNavArgs>;
export declare const JpSideNav: Story<SideNavArgs>;
export declare const JpDarkSideNav: Story<SideNavArgs>;
export declare const FooterImg: Story<SideNavArgs>;
