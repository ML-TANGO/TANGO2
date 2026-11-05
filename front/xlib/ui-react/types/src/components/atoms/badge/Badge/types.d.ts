/// <reference types="react" />
export interface BadgeArgs {
    label?: string;
    type?: string;
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
    radius?: 'default';
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
    leftIconVisible?: boolean;
    rightIconVisible?: boolean;
}
declare type BadgeTypes = 'blue' | 'primary-1' | 'primary-2' | 'red' | 'orange' | 'yellow' | 'green' | 'gray' | 'pink' | 'reserved' | 'installing' | 'expired' | 'error' | 'disabled';
declare const BadgeTypes: {
    readonly blue: "blue";
    readonly primary1: "primary-1";
    readonly primary2: "primary-2";
    readonly red: "red";
    readonly orange: "orange";
    readonly yellow: "yellow";
    readonly green: "green";
    readonly gray: "gray";
    readonly pink: "pink";
    readonly reserved: "reserved";
    readonly installing: "installing";
    readonly expired: "expired";
    readonly error: "error";
    readonly disabled: "disabled";
};
export { BadgeTypes };
export declare const BadgeInit: BadgeArgs;
