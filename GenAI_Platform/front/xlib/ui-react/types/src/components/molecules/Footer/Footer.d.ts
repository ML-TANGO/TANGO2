export interface FooterArgs {
    theme?: ThemeType;
    isOpen?: boolean;
    logoIcon?: any;
    copyrights?: string;
    updated?: string;
    language?: JSX.Element;
}
/**
 * Footer 컴포넌트
 */
declare function Footer({ theme, isOpen, logoIcon: LogoIcon, copyrights, updated, language, }: FooterArgs): JSX.Element;
declare namespace Footer {
    var defaultProps: {
        theme: "jp-primary";
        isOpen: boolean;
        logoIcon: undefined;
        copyrights: string;
        updated: string;
        language: undefined;
    };
}
export default Footer;
