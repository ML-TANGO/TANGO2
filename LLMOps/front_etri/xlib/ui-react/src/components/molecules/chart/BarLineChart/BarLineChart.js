import { jsx } from 'react/jsx-runtime';
import { useRef, useEffect } from 'react';
import { BarLineChart as ju } from '../../../../../packages/ui/ui-graph/pack/index.js';

function BarLineChart(_a) {
    var data = _a.data, width = _a.width, height = _a.height, minXAxis = _a.minXAxis, minYAxis = _a.minYAxis, maxXAxis = _a.maxXAxis, maxYAxis = _a.maxYAxis, unitsPerTickX = _a.unitsPerTickX, unitsPerTickY = _a.unitsPerTickY, axisColor = _a.axisColor, point = _a.point, barWidth = _a.barWidth, lineChartColor = _a.lineChartColor, barChartColor = _a.barChartColor, drawXAxis = _a.drawXAxis, drawXValue = _a.drawXValue, drawXTick = _a.drawXTick, drawYAxis = _a.drawYAxis, drawYValue = _a.drawYValue, drawYTick = _a.drawYTick, activeTooltip = _a.activeTooltip, tooltipStyle = _a.tooltipStyle, isAxisDraw = _a.isAxisDraw, background = _a.background;
    var canvasRef = useRef(null);
    useEffect(function () {
        var canvas = canvasRef.current;
        if (canvas && (data === null || data === void 0 ? void 0 : data.data)) {
            var param = {
                canvas: canvas,
                data: data,
                width: width,
                height: height,
                minXAxis: minXAxis,
                minYAxis: minYAxis,
                maxXAxis: maxXAxis,
                maxYAxis: maxYAxis,
                unitsPerTickX: unitsPerTickX,
                unitsPerTickY: unitsPerTickY,
                axisColor: axisColor,
                point: point,
                barWidth: barWidth,
                lineChartColor: lineChartColor,
                barChartColor: barChartColor,
                isAxisDraw: isAxisDraw,
                background: background,
            };
            var barLineChart = new ju(param);
            var drawParam = {
                drawXAxis: drawXAxis,
                drawXValue: drawXValue,
                drawXTick: drawXTick,
                drawYAxis: drawYAxis,
                drawYValue: drawYValue,
                drawYTick: drawYTick,
                activeTooltip: activeTooltip,
                tooltipStyle: tooltipStyle,
            };
            barLineChart.draw(drawParam);
        }
    }, [
        canvasRef,
        activeTooltip,
        axisColor,
        barChartColor,
        barWidth,
        data,
        drawXAxis,
        drawXTick,
        drawXValue,
        drawYAxis,
        drawYTick,
        drawYValue,
        height,
        lineChartColor,
        maxXAxis,
        maxYAxis,
        minXAxis,
        minYAxis,
        point,
        tooltipStyle,
        unitsPerTickX,
        unitsPerTickY,
        width,
        isAxisDraw,
        background,
    ]);
    return jsx("canvas", { ref: canvasRef });
}
BarLineChart.defaultProps = {
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
    point: undefined,
    barWidth: undefined,
    lineChartColor: undefined,
    barChartColor: undefined,
    drawXAxis: undefined,
    drawXValue: undefined,
    drawXTick: undefined,
    drawYAxis: undefined,
    drawYValue: undefined,
    drawYTick: undefined,
    activeTooltip: undefined,
    tooltipStyle: undefined,
    isAxisDraw: undefined,
    background: undefined,
};

export { BarLineChart as default };
//# sourceMappingURL=BarLineChart.js.map
