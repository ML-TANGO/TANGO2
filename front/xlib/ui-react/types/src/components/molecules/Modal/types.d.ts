export interface ModalArgs {
    headerProps?: any;
    footerProps?: any;
    contentProps?: any;
    headerStyle?: {
        [key: string]: string;
    };
    contentStyle?: {
        [key: string]: string;
    };
    footerStyle?: {
        [key: string]: string;
    };
    topAnimation?: string;
    theme?: ThemeType;
}
