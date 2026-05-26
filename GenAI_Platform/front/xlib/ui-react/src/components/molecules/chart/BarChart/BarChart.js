import { jsx } from 'react/jsx-runtime';
import { useRef, useEffect } from 'react';
import { BarChart as Iu } from '../../../../../packages/ui/ui-graph/pack/index.js';

function BarChart(_a) {
    var data = _a.data, width = _a.width, height = _a.height, minXAxis = _a.minXAxis, minYAxis = _a.minYAxis, maxXAxis = _a.maxXAxis, maxYAxis = _a.maxYAxis, unitsPerTickX = _a.unitsPerTickX, unitsPerTickY = _a.unitsPerTickY, axisColor = _a.axisColor, barWidth = _a.barWidth, barColor = _a.barColor, isAxisDraw = _a.isAxisDraw, drawXAxis = _a.drawXAxis, drawXValue = _a.drawXValue, drawXTick = _a.drawXTick, drawYAxis = _a.drawYAxis, drawYValue = _a.drawYValue, drawYTick = _a.drawYTick, background = _a.background;
    var canvasRef = useRef(null);
    useEffect(function () {
        var canvas = canvasRef.current;
        if (canvas && (data === null || data === void 0 ? void 0 : data.data)) {
            var param = {
                canvas: canvas,
                data: data,
                width: width,
                height: height,
                maxXAxis: maxXAxis,
                minXAxis: minXAxis,
                maxYAxis: maxYAxis,
                minYAxis: minYAxis,
                unitsPerTickX: unitsPerTickX,
                unitsPerTickY: unitsPerTickY,
                axisColor: axisColor,
                barWidth: barWidth,
                barColor: barColor,
                isAxisDraw: isAxisDraw,
                background: background,
            };
            var barChart = new Iu(param);
            var drawParam = {
                drawXAxis: drawXAxis,
                drawXValue: drawXValue,
                drawXTick: drawXTick,
                drawYAxis: drawYAxis,
                drawYValue: drawYValue,
                drawYTick: drawYTick,
            };
            barChart.draw(drawParam);
        }
    }, [
        data,
        width,
        height,
        minXAxis,
        minYAxis,
        maxXAxis,
        maxYAxis,
        unitsPerTickX,
        unitsPerTickY,
        axisColor,
        barWidth,
        barColor,
        isAxisDraw,
        drawXAxis,
        drawXValue,
        drawXTick,
        drawYAxis,
        drawYValue,
        drawYTick,
        background,
    ]);
    return jsx("canvas", { ref: canvasRef });
}
BarChart.defaultProps = {
    data: [],
    width: undefined,
    height: undefined,
    minXAxis: undefined,
    minYAxis: undefined,
    maxXAxis: undefined,
    maxYAxis: undefined,
    unitsPerTickX: undefined,
    unitsPerTickY: undefined,
    axisColor: undefined,
    barWidth: undefined,
    barColor: undefined,
    drawXAxis: undefined,
    drawXValue: undefined,
    drawXTick: undefined,
    drawYAxis: undefined,
    drawYValue: undefined,
    drawYTick: undefined,
    isAxisDraw: undefined,
    background: undefined,
};

export { BarChart as default };
//# sourceMappingURL=BarChart.js.map
