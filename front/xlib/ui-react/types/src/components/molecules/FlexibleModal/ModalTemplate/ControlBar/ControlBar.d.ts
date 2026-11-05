declare type ControlBarProps = {
    isFullScreen: boolean;
    onClickClose: () => void;
    onClickMinimize: () => void;
    onClickFullScreen: () => void;
    minimize: boolean;
    fullscreen: boolean;
};
export default function ControlBar({ minimize, fullscreen, isFullScreen, onClickClose, onClickMinimize, onClickFullScreen, }: ControlBarProps): JSX.Element;
export {};
