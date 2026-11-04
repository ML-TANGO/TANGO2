import { jsx } from 'react/jsx-runtime';
import { useMemo, useEffect } from 'react';
import { CanvasLineChart as Vu } from '../../../../../packages/ui/ui-graph/pack/index.js';

function CanvasLineChart(_a) {
    var id = _a.id, series = _a.series, axis = _a.axis, width = _a.width, height = _a.height, pointSize = _a.pointSize, font = _a.font, fontHeight = _a.fontHeight, canvasStyle = _a.canvasStyle, renderOption = _a.renderOption;
    var chart = useMemo(function () {
        var param = {
            nodeId: id,
            width: width,
            height: height,
            point: pointSize,
            font: font,
            fontHeight: fontHeight,
            canvasStyle: canvasStyle,
        };
        return new Vu(param);
    }, [id, canvasStyle, font, fontHeight, height, pointSize, width]);
    useEffect(function () {
        if (chart) {
            var param = {
                series: series,
                axis: axis,
            };
            chart.dataInitialize(param);
            var unmount_1 = chart.render(renderOption);
            return function () {
                if (unmount_1)
                    unmount_1();
            };
        }
        return undefined;
    }, [axis, chart, series, renderOption]);
    return jsx("div", { id: id });
}
CanvasLineChart.defaultProps = {
    width: 1800,
    height: 700,
    pointSize: 3,
    font: 'normal bold 12px serif',
    fontHeight: 12,
    canvasStyle: undefined,
    renderOption: {
        bottomAxis: true,
        bottomTick: true,
        bottomText: true,
        leftAxis: true,
        leftTick: true,
        leftText: true,
        rightAxis: true,
        rightTick: true,
        rightText: true,
        tooltip: true,
        guideLine: true,
    },
};

export { CanvasLineChart as default };
//# sourceMappingURL=CanvasLineChart.js.map
