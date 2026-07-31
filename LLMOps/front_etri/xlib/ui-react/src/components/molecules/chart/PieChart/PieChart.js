import { jsx } from 'react/jsx-runtime';
import { useRef, useEffect } from 'react';
import { PieChart as Ru } from '../../../../../packages/ui/ui-graph/pack/index.js';

function PieChart(_a) {
    var data = _a.data, chartSize = _a.chartSize, chartFillColor = _a.chartFillColor, chartBolder = _a.chartBolder, centerText = _a.centerText, totalValue = _a.totalValue;
    var canvas = useRef(null);
    useEffect(function () {
        if (canvas.current) {
            var param = {
                canvas: canvas.current,
                data: data,
                chartSize: chartSize,
                chartFillColor: chartFillColor,
                chartBolder: chartBolder,
                centerText: centerText,
                totalValue: totalValue,
            };
            var pieChart = new Ru(param);
            pieChart.draw();
        }
    }, [centerText, chartBolder, chartFillColor, chartSize, data, totalValue]);
    return jsx("canvas", { ref: canvas });
}

export { PieChart as default };
//# sourceMappingURL=PieChart.js.map
