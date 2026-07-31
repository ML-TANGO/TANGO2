interface ContentsType {
    title: string;
    subject: string;
    desc: string;
    tabContent: string;
    category: string;
    type: string;
    code: string;
}
interface CategoryType {
    DEFAULT: string;
    CANVAS_LINE: string;
    CANVAS_PIE: string;
    D3_LINE: string;
}
declare const category: CategoryType;
export { ContentsType, CategoryType, category };
