import { PagingHookArgs } from './types';
declare const usePaiging: ({ dataSize, rowSize, pagingBtnAlign, PagingBtn, }: PagingHookArgs) => [number, () => JSX.Element];
export default usePaiging;
