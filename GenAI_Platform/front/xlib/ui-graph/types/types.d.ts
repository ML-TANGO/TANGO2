export interface ObjectType {
    [key: string]: any;
}
export interface GuideRenderType {
    title: string;
    desc: string;
    tabs: {
        tabName: string;
        tabContent: string[];
        code: boolean;
    }[];
    render: () => void;
}
export interface Vector {
    x: number;
    y: number;
}
