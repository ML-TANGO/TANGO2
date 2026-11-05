import { Story } from '@storybook/react';
import PieChart from './PieChart';
import { PieChartArgs } from './types';
declare const _default: {
    title: string;
    component: typeof PieChart;
    parameters: {
        componentSubtitle: string;
    };
    argTypes: {
        chartSize: {
            control: {
                disable: boolean;
            };
        };
        data: {
            control: {
                disable: boolean;
            };
        };
    };
};
export default _default;
export declare const PrimaryPieChart: Story<PieChartArgs>;
