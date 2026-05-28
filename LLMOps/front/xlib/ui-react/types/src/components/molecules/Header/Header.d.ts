export interface HeaderArgs {
    expandHandler?: () => void;
    hideMenuBtn?: boolean;
    theme?: ThemeType;
    leftBoxContents?: Array<JSX.Element>;
    rightBoxContents?: Array<JSX.Element>;
    isLogo?: boolean;
    logoIcon?: any;
}
/**
 * Header 컴포넌트
 */
declare function Header({ expandHandler, hideMenuBtn, theme, leftBoxContents, rightBoxContents, isLogo, logoIcon: LogoIcon, }: HeaderArgs): JSX.Element;
declare namespace Header {
    var defaultProps: {
        expandHandler: () => void;
        hideMenuBtn: boolean;
        theme: "jp-primary";
        leftBoxContents: never[];
        rightBoxContents: never[];
        isLogo: boolean;
        logoIcon: string;
    };
}
export default Header;
