/// <reference types="react" />
export interface CheckboxArgs {
    disabled?: boolean;
    label?: string;
    readonly onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}
export declare const CheckboxInit: CheckboxArgs;
