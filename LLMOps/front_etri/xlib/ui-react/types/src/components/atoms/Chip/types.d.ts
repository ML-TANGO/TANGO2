/// <reference types="react" />
interface ChipArgs {
    id?: string;
    label: string;
    onClick: (e: React.MouseEvent<HTMLButtonElement>, id?: string) => void;
}
export { ChipArgs };
