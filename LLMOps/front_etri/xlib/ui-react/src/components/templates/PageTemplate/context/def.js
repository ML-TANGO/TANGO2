import { __assign } from '../../../../../_virtual/_tslib.js';

var initialPageTemplateState = {
    isOpen: true,
};
function pageTemplateReducer(state, action) {
    switch (action.type) {
        case 'OPEN': {
            return __assign(__assign({}, state), { isOpen: true });
        }
        case 'CLOSE': {
            return __assign(__assign({}, state), { isOpen: false });
        }
        default: {
            return __assign(__assign({}, state), { isOpen: false });
        }
    }
}

export { initialPageTemplateState, pageTemplateReducer };
//# sourceMappingURL=def.js.map
