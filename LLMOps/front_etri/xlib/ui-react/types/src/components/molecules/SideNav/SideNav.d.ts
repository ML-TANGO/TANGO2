import i18n from 'react-i18next';
export interface SideNavArgs {
    width?: number;
    responsive?: boolean;
    theme?: ThemeType;
    navList?: Array<{
        name: string;
        path: string;
        icon?: any;
        activeIcon?: any;
    }>;
    mode?: string;
    isManual?: boolean;
    isHideManual?: boolean;
    mainNavComponent?: any;
    onNavigate: ({ element, path, isActive, activeClassName, }: {
        element: JSX.Element;
        path: string;
        isActive: (match: any) => boolean;
        activeClassName: string;
    }) => JSX.Element;
    onServiceManual?: (service: string) => void;
    footerRender?: () => JSX.Element;
    t?: i18n.TFunction<'translation'>;
}
/**
 * 사이드 네비게이션 컴포넌트
 */
declare function SideNav({ width, mainNavComponent, responsive, theme, navList, mode, isManual, isHideManual, onNavigate, footerRender, onServiceManual, t, }: SideNavArgs): JSX.Element;
declare namespace SideNav {
    var defaultProps: {
        width: undefined;
        mainNavComponent: null;
        responsive: boolean;
        navList: never[];
        mode: undefined;
        isManual: boolean;
        isHideManual: boolean;
        theme: "jp-primary";
        onServiceManual: () => void;
        footerRender: undefined;
        t: undefined;
    };
}
export default SideNav;
