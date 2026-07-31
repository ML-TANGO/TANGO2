/// <reference types="react" />
declare type Props = {
    label: string;
    id?: string;
    size?: 'xs' | 'sm' | 'md' | 'lg';
    readonly onClick?: (e: React.MouseEvent<HTMLButtonElement>, id?: string) => void;
};
declare const Chip: {
    ({ label, id, size, onClick }: Props): JSX.Element;
    defaultProps: {
        id: string;
        size: string;
        onClick: () => void;
    };
};
export default Chip;
