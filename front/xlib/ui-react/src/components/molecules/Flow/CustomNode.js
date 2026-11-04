import { __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, Fragment, jsx } from 'react/jsx-runtime';
import { memo } from 'react';
import { Handle as Handle$1 } from '../../../../modules/react-flow-renderer/dist/esm/index.js';
import broadcastingSuccess from '../../../static/images/icons/broadcastingSuccess.svg.js';
import errorIcon from '../../../static/images/icons/error-icon.svg.js';
import style from './Flow.module.scss.js';
import classNames from '../../../../modules/classnames/bind.js';

var cx = classNames.bind(style);
var CustomNode = memo(function (_a) {
    var _b;
    var data = _a.data, isConnectable = _a.isConnectable;
    var colorClass = '';
    if (data.testStatus === 2 && data.trainingStatus === 2) {
        colorClass = 'darkLime';
    }
    else if (data.testStatus < 2 && data.trainingStatus <= 2) {
        colorClass = 'blue';
    }
    return (jsxs(Fragment, { children: [jsxs("div", __assign({ className: cx('span-container') }, { children: [jsx("div", __assign({ className: cx('client-thumbnail-container') }, { children: jsx("p", __assign({ className: cx('client-thumbnail-name') }, { children: (_b = data.clientName) === null || _b === void 0 ? void 0 : _b.charAt(0) })) })), jsx("p", __assign({ className: cx('client-name') }, { children: data.clientName })), jsxs("div", { children: [data.dotPosition === 'right' &&
                                data.trainingStatus !== 3 &&
                                (data.metrics ? (jsx("div", __assign({ className: cx('box', colorClass) }, { children: jsx("p", __assign({ className: cx('client-number') }, { children: data.metrics && data.metrics })) }))) : (jsx("div", __assign({ className: cx('box', colorClass) }, { children: jsxs("div", __assign({ className: cx('container') }, { children: [jsx("span", { className: cx('circle') }), jsx("span", { className: cx('circle') }), jsx("span", { className: cx('circle') })] })) })))), data.trainingStatus === 3 && (jsx("div", __assign({ className: cx('error-status-icon') }, { children: jsx("img", { src: errorIcon, alt: '' }) }))), data.dotPosition === 'left' && data.broadcastingStatus === 2 && (jsx("div", __assign({ className: cx('status-icon') }, { children: jsx("img", { src: broadcastingSuccess, alt: '' }) })))] })] })), jsx(Handle$1, { type: data.dotPosition === 'right' ? 'source' : 'target', position: data.dotPosition, id: 'clientNode', isConnectable: isConnectable })] }));
});

export { CustomNode as default };
//# sourceMappingURL=CustomNode.js.map
