import { Story } from '@storybook/react';
import CanvasLineChart from './CanvasLineChart';
import { CanvasLineChartArgs } from './types';
declare const _default: {
    title: string;
    component: typeof CanvasLineChart;
    parameters: {
        componentSubtitle: string;
    };
};
export default _default;
export declare const SingleLineChart: Story<CanvasLineChartArgs>;
export declare const MultiLineChart: Story<CanvasLineChartArgs>;
export declare const MultiAxisChart: Story<CanvasLineChartArgs>;
