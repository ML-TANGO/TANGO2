import { jsx } from 'react/jsx-runtime';
import { useMemo, useEffect } from 'react';
import { LineChart as Yu } from '../../../../../../packages/ui/ui-graph/pack/index.js';

function SingleLineChart(_a) {
    var id = _a.id, width = _a.width, height = _a.height, isResponsive = _a.isResponsive, legend = _a.legend, series = _a.series, data = _a.data, xTickFormat = _a.xTickFormat;
    var lineChart = useMemo(function () {
        return new Yu({
            eleId: id,
            width: width,
            height: height,
            isResponsive: isResponsive,
            legend: legend,
            xAxisMaxTicks: 6,
            tooltip: {
                align: 'right',
            },
        });
    }, [height, id, isResponsive, legend, width]);
    useEffect(function () {
        if (lineChart) {
            lineChart.init(data);
            lineChart.setSeries(series);
            lineChart.draw();
        }
    }, [lineChart, data, series]);
    useEffect(function () {
        if (lineChart) {
            lineChart.updateOption({
                width: width,
                height: height,
                isResponsive: isResponsive,
                legend: legend,
                xTickFormat: xTickFormat,
            });
            lineChart.draw(data);
        }
    }, [lineChart, data, width, height, isResponsive, legend, xTickFormat]);
    return jsx("div", { id: id });
}

export { SingleLineChart as default };
//# sourceMappingURL=SingleLineChart.js.map
