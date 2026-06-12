interface NavItemArgs {
    name: string;
    path: string;
    icon: any;
    activeIcon: any;
    group: string | undefined;
    subGroup: string | undefined;
    isGroup: boolean | undefined;
    onNavigate: ({ element, path, isActive, activeClassName, }: {
        element: JSX.Element;
        path: string;
        isActive: (match: any) => boolean;
        activeClassName: string;
    }) => JSX.Element;
    theme?: ThemeType;
}
declare function NavItem({ name, path, icon: Icon, activeIcon: ActiveIcon, group, subGroup, isGroup, onNavigate, theme, }: NavItemArgs): JSX.Element;
declare namespace NavItem {
    var defaultProps: {
        theme: "jp-primary";
    };
}
export default NavItem;
