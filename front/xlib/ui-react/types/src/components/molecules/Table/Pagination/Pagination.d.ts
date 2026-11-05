import { PaginationArgs } from '../types';
declare function Pagination({ loc, pagingBtnAlign, PagingBtn, pageHandler, moveEdgePage, }: PaginationArgs): JSX.Element;
declare namespace Pagination {
    var defaultProps: {
        pagingBtnAlign: string;
        PagingBtn: {
            MoveFirst: undefined;
            MoveLast: undefined;
            MovePrev: () => JSX.Element;
            MoveNext: () => JSX.Element;
        };
    };
}
export default Pagination;
