import { ModalTemplateArgs } from '@src/components/molecules/FlexibleModal/types';
export declare type CreateModalArgs = {
    title: string;
    fullscreen: boolean;
    content: JSX.Element;
    startOnFullScreen?: boolean;
};
declare function useModal(): {
    createModal: ({ fullscreen, title, content, startOnFullScreen, }: CreateModalArgs) => void;
    closeAll: () => void;
    close: (key: string) => void;
    modalList: ModalTemplateArgs[];
    modalKey: string;
};
export { useModal };
