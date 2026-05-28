import { __read, __assign } from '../../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { createContext, useReducer, useMemo } from 'react';
import { pageTemplateReducer, initialPageTemplateState } from './def.js';

var PageTemplateContext = createContext({});
var PageTemplateContextProvider = function (_a) {
    var children = _a.children;
    var _b = __read(useReducer(pageTemplateReducer, initialPageTemplateState), 2), pageState = _b[0], pageTemplateDispatch = _b[1];
    var value = useMemo(function () { return ({
        isOpen: pageState.isOpen,
        pageTemplateDispatch: pageTemplateDispatch,
    }); }, [pageState.isOpen]);
    return (jsx(PageTemplateContext.Provider, __assign({ value: value }, { children: children })));
};

export { PageTemplateContext, PageTemplateContextProvider };
//# sourceMappingURL=context.js.map
