import { Story } from '@storybook/react';
import Icon from './Icon';
import { IconArgs } from './IconTypes';
declare const _default: {
    title: string;
    component: typeof Icon;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        viewAllIcons: {
            control: {
                disable: boolean;
            };
        };
        IconCompoList: {
            control: {
                disable: boolean;
            };
        };
        name: {
            control: {
                disable: boolean;
            };
        };
    };
};
export default _default;
export declare const AllIcons: Story<IconArgs>;
export declare const IconLnbDatasetsBlueCompo: Story<IconArgs>;
export declare const IconLnbDatasetsWhiteCompo: Story<IconArgs>;
export declare const IconLnbDeploymentsBlueCompo: Story<IconArgs>;
export declare const IconLnbDeploymentsWhiteCompo: Story<IconArgs>;
export declare const IconLnbDockerBlueCompo: Story<IconArgs>;
export declare const IconLnbDockerWhiteCompo: Story<IconArgs>;
export declare const IconLnbHomeBlueCompo: Story<IconArgs>;
export declare const IconLnbHomeWhiteIcon: Story<IconArgs>;
export declare const IconLnbServicesBlueCompo: Story<IconArgs>;
export declare const IconLnbServicesWhiteCompo: Story<IconArgs>;
export declare const IconLnbTrainingsBlueCompo: Story<IconArgs>;
export declare const IconLnbTrainingsWhiteCompo: Story<IconArgs>;
