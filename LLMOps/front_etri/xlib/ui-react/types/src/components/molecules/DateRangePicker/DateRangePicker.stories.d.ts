import { Story } from '@storybook/react';
import DateRangePicker from './DateRangePicker';
import { DateRangePickerArgs } from './types';
declare const _default: {
    title: string;
    component: typeof DateRangePicker;
    parameter: {
        componentSubtitle: string;
    };
    argTypes: {
        inputSize: {
            options: string[];
            control: {
                type: string;
            };
        };
        calendarSize: {
            options: string[];
            control: {
                type: string;
            };
        };
        type: {
            control: {
                disable: boolean;
            };
        };
        status: {
            options: string[];
            control: {
                type: string;
            };
        };
        t: {
            control: {
                disable: boolean;
            };
        };
        onSubmit: {
            action: string;
        };
    };
};
export default _default;
export declare const PrimaryDateRangePicker: Story<DateRangePickerArgs>;
export declare const SplitInputDateRangePicker: Story<DateRangePickerArgs>;
