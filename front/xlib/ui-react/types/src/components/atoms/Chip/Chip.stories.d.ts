/// <reference types="react" />
import { Story } from '@storybook/react';
import { ChipArgs } from './types';
declare const _default: {
    title: string;
    component: {
        ({ label, id, size, onClick }: {
            label: string;
            id?: string | undefined;
            size?: "xs" | "sm" | "md" | "lg" | undefined;
            readonly onClick?: ((e: import("react").MouseEvent<HTMLButtonElement, MouseEvent>, id?: string | undefined) => void) | undefined;
        }): JSX.Element;
        defaultProps: {
            id: string;
            size: string;
            onClick: () => void;
        };
    };
    parameters: {
        componentSubtitle: string;
    };
};
export default _default;
export declare const PrimaryChip: Story<ChipArgs>;
