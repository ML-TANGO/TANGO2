import { __read, __assign } from '../../../../_virtual/_tslib.js';
import { jsxs, Fragment, jsx } from 'react/jsx-runtime';
import { memo, useState } from 'react';
import aggregationIcon from '../../../static/images/icons/aggregationIcon.svg.js';
import { Handle as Handle$1 } from '../../../../modules/react-flow-renderer/dist/esm/index.js';
import sameArrow from '../../../static/images/icons/same_arrow.svg.js';
import lowArrow from '../../../static/images/icons/low_arrow.svg.js';
import highArrow from '../../../static/images/icons/high_arrow.svg.js';
import errorIcon from '../../../static/images/icons/error-icon.svg.js';
import style from './Flow.module.scss.js';
import classNames from '../../../../modules/classnames/bind.js';

var cx = classNames.bind(style);
var Position;
(function (Position) {
    Position["Left"] = "left";
    Position["Top"] = "top";
    Position["Right"] = "right";
    Position["Bottom"] = "bottom";
})(Position || (Position = {}));
var MainNode = memo(function (data) {
    var _a = data.data, aggregationStatus = _a.aggregationStatus, metrics = _a.metrics, globalModelData = _a.globalModelData, metricLabel = _a.metricLabel, seedModelLabel = _a.seedModelLabel, resultModelLabel = _a.resultModelLabel, stageFailReason = _a.stageFailReason;
    var _b = __read(useState(false), 2), showTooltip = _b[0], setShowTooltip = _b[1];
    return (jsxs(Fragment, { children: [jsx(Handle$1, { type: 'target', position: Position.Left, id: 'left', style: { width: 0, height: 0 } }), globalModelData ? (jsxs("div", __assign({ className: cx('round-detail-aggregation') }, { children: [jsxs("div", __assign({ className: cx('round-detail-aggregation-cell-title') }, { children: [jsx("p", { children: metricLabel }), jsx("p", { children: seedModelLabel }), jsxs("p", { children: [resultModelLabel, aggregationStatus === 3 && (jsx("img", { className: cx('error-img'), src: errorIcon, alt: 'error-icon', onMouseOver: function () { return setShowTooltip(true); }, onMouseLeave: function () { return setShowTooltip(false); } })), showTooltip && stageFailReason && (jsx("p", __assign({ className: cx('error-message') }, { children: stageFailReason })))] })] })), jsx("div", __assign({ className: cx('global-model-data') }, { children: globalModelData === null || globalModelData === void 0 ? void 0 : globalModelData.map(function (data) {
                            return (jsxs("div", __assign({ className: cx('global-model-data-div') }, { children: [jsx("p", { children: data.metric }), jsx("p", { children: data.seedModel }), jsxs("p", { children: [aggregationStatus === 3 ? '-' : data.resultModel, data.change_direction === 'same' && (jsx("img", { src: sameArrow, alt: 'same arrow' })), data.change_direction === 'lower' && (jsx("img", { src: lowArrow, alt: 'low arrow' })), data.change_direction === 'higher' && (jsx("img", { src: highArrow, alt: 'high arrow' }))] })] }), data.metric));
                        }) }))] }))) : (jsxs("div", __assign({ className: cx(aggregationStatus === 2 && 'complete', aggregationStatus === 1 && 'block', 'mainNode-container') }, { children: [jsxs("div", __assign({ className: cx('aggregation-div') }, { children: [jsxs("div", __assign({ style: { display: 'grid' } }, { children: [aggregationStatus === 3 ? (jsx("img", { className: cx('aggregation-img'), src: errorIcon, alt: 'aggregation icon' })) : (jsx("img", { className: cx('aggregation-img'), src: aggregationIcon, alt: 'aggregation icon' })), aggregationStatus === 3 && (jsx("p", __assign({ className: cx('error-message') }, { children: stageFailReason })))] })), jsx("p", __assign({ className: cx('aggregation-text') }, { children: "Aggregation" }))] })), metrics && (jsx("div", __assign({ className: cx('round-metrics') }, { children: metrics === null || metrics === void 0 ? void 0 : metrics.map(function (data) {
                            return (jsxs("div", __assign({ className: cx('round-metrics-div') }, { children: [jsx("p", __assign({ className: cx('round-metrics-key') }, { children: data.key })), jsx("p", __assign({ className: cx('round-metrics-value') }, { children: data.value })), data.change_direction === 'same' && (jsx("img", { src: sameArrow, alt: 'same arrow' })), data.change_direction === 'lower' && (jsx("img", { src: lowArrow, alt: 'low arrow' })), data.change_direction === 'higher' && (jsx("img", { src: highArrow, alt: 'high arrow' }))] }), data.key));
                        }) })))] }))), jsx(Handle$1, { type: 'source', position: Position.Right, id: 'right', style: { width: 0, height: 0 } })] }));
});

export { MainNode as default };
//# sourceMappingURL=MainNode.js.map
