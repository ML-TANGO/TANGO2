import { ReactType, ReactDOM } from './types';
declare const React: ReactType;
export declare const useState: {
    <T>(initState: T): [T, (newVal: T) => void];
    <T_1 = undefined>(initState?: T_1 | undefined): [T_1 | undefined, (newVal: T_1 | undefined) => void];
}, useEffect: (effect: () => any, deps?: readonly any[] | undefined) => void, useDocument: (event: () => void) => void, useStateNoRender: {
    <T>(initState: T): [T, (newVal: T) => void];
    <T_1 = undefined>(initState?: T_1 | undefined): [T_1 | undefined, (newVal: T_1 | undefined) => void];
};
export { ReactDOM };
export default React;
