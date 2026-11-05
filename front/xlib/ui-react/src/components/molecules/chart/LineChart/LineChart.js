import { jsx } from 'react/jsx-runtime';
import { chartTypes } from './types.js';
import SingleLineChart from './SingleLineChart/SingleLineChart.js';
import MultiLineChart from './MultiLineChart/MultiLineChart.js';

function LineChart(_a) {
    // if (type === chartTypes.FILLED) {
    //   return <FilledLineChart data={data} />;
    // }
    var _b = _a.id, id = _b === void 0 ? '' : _b, _c = _a.type, type = _c === void 0 ? chartTypes.SINGLE : _c, _d = _a.width, width = _d === void 0 ? 800 : _d, _e = _a.height, height = _e === void 0 ? 300 : _e, _f = _a.isResponsive, isResponsive = _f === void 0 ? true : _f, _g = _a.legend, legend = _g === void 0 ? true : _g, _h = _a.series, series = _h === void 0 ? [] : _h, data = _a.data, xTickFormat = _a.xTickFormat;
    if (type === chartTypes.MULTI) {
        return (jsx(MultiLineChart, { id: id, width: width, height: height, isResponsive: isResponsive, legend: legend, series: series, data: data, xTickFormat: xTickFormat }));
    }
    return (jsx(SingleLineChart, { id: id, width: width, height: height, isResponsive: isResponsive, legend: legend, series: series, data: data, xTickFormat: xTickFormat }));
}
LineChart.defaultProps = {
    id: '',
    type: chartTypes.SINGLE,
    width: 800,
    height: 300,
    isResponsive: true,
    legend: true,
    series: undefined,
};

export { LineChart as default };
//# sourceMappingURL=LineChart.js.map
