export interface PageTemplateState {
    isOpen: boolean;
}
export interface PageTemplateAction {
    type: 'CLOSE' | 'OPEN';
}
export interface PageTemplateValue {
    isOpen: boolean;
    pageTemplateDispatch: any;
}
