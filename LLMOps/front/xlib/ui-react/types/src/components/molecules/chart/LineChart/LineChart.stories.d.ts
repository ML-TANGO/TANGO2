import { Story } from '@storybook/react';
import LineChart from './LineChart';
import { LineChartArgs } from './types';
declare const _default: {
    title: string;
    component: typeof LineChart;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        width: {
            control: {
                type: string;
            };
        };
        type: {
            control: {
                disable: boolean;
            };
        };
        height: {
            control: {
                type: string;
            };
        };
        id: {
            control: {
                disable: boolean;
            };
        };
        isResponsive: {
            control: {
                type: string;
            };
        };
    };
};
export default _default;
export declare const SingleLineChart: Story<LineChartArgs>;
export declare const MultiLineChart: Story<LineChartArgs>;
