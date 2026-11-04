import { Story } from '@storybook/react';
import StatusCard from './StatusCard';
import { StatusCardArgs } from './types';
declare const _default: {
    title: string;
    component: typeof StatusCard;
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
export declare const RunningStatusCard: Story<StatusCardArgs>;
export declare const PendingStatusCard: Story<StatusCardArgs>;
export declare const DoneStatusCard: Story<StatusCardArgs>;
export declare const ErrorStatusCard: Story<StatusCardArgs>;
export declare const UnknownStatusCard: Story<StatusCardArgs>;
