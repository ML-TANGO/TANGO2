import i18n from 'react-i18next';
export interface NavArgs {
    navList?: Array<{
        name: string;
        path: string;
        icon?: any;
        activeIcon?: any;
        isGroup?: boolean;
        isFirstGroup?: boolean;
        isLastGroup?: boolean;
        group?: string;
        subGroup?: string;
        disabled?: boolean;
    }>;
    theme?: ThemeType;
    onNavigate: ({ element, path, isActive, activeClassName, }: {
        element: JSX.Element;
        path: string;
        isActive: (match: any) => boolean;
        activeClassName: string;
    }) => JSX.Element;
    t?: i18n.TFunction<'translation'>;
}
declare function Nav({ navList, theme, onNavigate, t }: NavArgs): JSX.Element;
declare namespace Nav {
    var defaultProps: {
        navList: never[];
        theme: "jp-primary";
        t: undefined;
    };
}
export default Nav;
