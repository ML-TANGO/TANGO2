export interface ModalTemplateArgs {
    onClickClose: (modalKey: string) => void;
    onClickMinimize?: (modalKey: string) => void;
    onClickMaximize?: (modalKey: string) => void;
    onClickFullScreen?: (modalKey: string) => void;
    onClickWindowSize?: (modalKey: string) => void;
    size?: 'sm' | 'md' | 'lg';
    theme?: ThemeType;
    title?: string;
    isOpen?: boolean;
    control?: boolean;
    content?: JSX.Element;
    modalKey: string;
    isFullScreen?: boolean;
    isMinimize?: boolean;
    isMaximize?: boolean;
    minimize?: boolean;
    fullscreen?: boolean;
    startFullscreen?: boolean;
}
export interface ModalHeaderArgs {
    title: string;
}
export interface ModalButtonModel {
    title: string;
    disabled?: boolean;
    onClick?: () => void;
}
export interface ModalButtonsArgs {
    okButton?: ModalButtonModel;
    prevButton?: ModalButtonModel;
    nextButton?: ModalButtonModel;
    cancelButton?: ModalButtonModel;
}
export interface ModalContentArgs {
    modalKey: string;
}
