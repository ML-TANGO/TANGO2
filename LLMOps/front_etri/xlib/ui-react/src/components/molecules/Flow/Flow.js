import { __read, __assign } from '../../../../_virtual/_tslib.js';
import { jsx } from 'react/jsx-runtime';
import { useState, useCallback, useEffect } from 'react';
import ReactFlow from '../../../../modules/react-flow-renderer/dist/esm/index.js';
import MainNode from './MainNode.js';
import CustomNode from './CustomNode.js';
import { i as index } from '../../../../modules/react-flow-renderer/dist/esm/index-2fe4e143.js';

var nodeTypes = {
    customNode: CustomNode,
    mainNode: MainNode,
};
var LEFT = 'left';
var RIGHT = 'right';
var DARK_MONO = '#5F5F5F';
var DARK_BLUE = '#2D76F8';
var DARK_LIME = '#27D478';
function Flow(_a) {
    var data = _a.data, width = _a.width, height = _a.height, metricLabel = _a.metricLabel, seedModelLabel = _a.seedModelLabel, resultModelLabel = _a.resultModelLabel;
    var _b = __read(useState(), 2), nodes = _b[0], setNodes = _b[1];
    var _c = __read(useState(), 2), edges = _c[0], setEdges = _c[1];
    var broadcastingStageStatus = data.broadcastingStageStatus, trainingStageStatus = data.trainingStageStatus, globalModelData = data.globalModelData, aggregationStatus = data.aggregationStatus, metrics = data.metrics, stageFailReason = data.stageFailReason;
    var createEdge = useCallback(function (nodeArray) {
        var edgeArray = [];
        nodeArray.forEach(function (data, index) {
            var nodeLineColor = '';
            var animatedState = false;
            var lineColorCheckData = data.sourcePosition === LEFT
                ? trainingStageStatus
                : broadcastingStageStatus;
            if (lineColorCheckData === 0) {
                nodeLineColor = DARK_MONO;
                animatedState = false;
            }
            else if (lineColorCheckData === 1) {
                nodeLineColor = DARK_BLUE;
                animatedState = true;
            }
            else if (lineColorCheckData === 2) {
                nodeLineColor = DARK_LIME;
                animatedState = false;
            }
            var edge = {
                id: "edge".concat(index),
                source: data.sourcePosition === LEFT ? data.id : 'mainNode',
                target: data.sourcePosition === LEFT ? 'mainNode' : data.id,
                style: { stroke: nodeLineColor, strokeWidth: 3 },
                type: 'smoothstep',
                className: 'smoothstep edge',
                animated: animatedState,
            };
            edgeArray.push(edge);
        });
        setEdges(edgeArray);
    }, [broadcastingStageStatus, trainingStageStatus]);
    var createNode = useCallback(function () {
        var dataValues = data.data;
        var nodeArray = [];
        var rightX = 610;
        var leftX = 0;
        var y = 0;
        var SumData = 60;
        var mainNodeY = 0;
        // aggregation Node(mainNode) position
        if (data.metrics) {
            mainNodeY = -79;
            if (dataValues.length === 1)
                mainNodeY = -76.5;
            else if (dataValues.length === 2)
                mainNodeY = -47;
            else
                mainNodeY += (dataValues.length - 1) * 31;
        }
        else if (globalModelData) {
            // round Detail poistion
            rightX = 800;
            mainNodeY = -100;
            if (dataValues.length === 1)
                mainNodeY = -97;
            else if (dataValues.length === 2)
                mainNodeY = -65;
            else
                mainNodeY += (dataValues.length - 1) * 31;
        }
        else {
            if (dataValues.length === 1)
                mainNodeY = -14;
            else if (dataValues.length === 2)
                mainNodeY = 14;
            else
                mainNodeY = 11 + (dataValues.length - 2) * 30;
        }
        nodeArray.push({
            id: 'mainNode',
            type: 'mainNode',
            data: {
                type: LEFT,
                aggregationStatus: aggregationStatus,
                metrics: metrics,
                globalModelData: globalModelData,
                metricLabel: metricLabel,
                seedModelLabel: seedModelLabel,
                resultModelLabel: resultModelLabel,
                stageFailReason: stageFailReason,
            },
            position: {
                x: 330,
                y: mainNodeY,
            },
        });
        dataValues.forEach(function (dataValue, index) {
            var trainingStatus = dataValue.trainingStatus, testStatus = dataValue.testStatus, metrics = dataValue.metrics, broadcastingStatus = dataValue.broadcastingStatus;
            var leftNode = {
                id: "leftNode".concat(index),
                type: 'customNode',
                data: {
                    dotPosition: RIGHT,
                    clientName: dataValue.clientName,
                    trainingStatus: trainingStatus,
                    testStatus: testStatus,
                    metrics: metrics,
                },
                position: { x: leftX, y: y },
                sourcePosition: LEFT,
            };
            var rightNode = {
                id: "rightNode".concat(index),
                type: 'customNode',
                data: {
                    dotPosition: LEFT,
                    clientName: dataValue.clientName,
                    broadcastingStatus: broadcastingStatus,
                },
                position: { x: rightX, y: y },
                sourcePosition: RIGHT,
            };
            y += SumData;
            nodeArray.push(leftNode, rightNode);
        });
        setNodes(nodeArray);
        createEdge(nodeArray);
    }, [
        aggregationStatus,
        createEdge,
        data,
        globalModelData,
        metricLabel,
        metrics,
        resultModelLabel,
        seedModelLabel,
        stageFailReason,
    ]);
    useEffect(function () {
        createNode();
    }, [createNode]);
    return (jsx("div", __assign({ style: {
            height: height,
            width: width,
        } }, { children: jsx(ReactFlow, __assign({ nodes: nodes, edges: edges, snapToGrid: true, nodeTypes: nodeTypes, defaultZoom: 1.5, maxZoom: 1.4, minZoom: 0.8, preventScrolling: false, fitView: true, fitViewOptions: {
                includeHiddenNodes: false,
            }, zoomOnScroll: false, onlyRenderVisibleElements: true }, { children: jsx(index, { showInteractive: false }) })) })));
}

export { Flow as default };
//# sourceMappingURL=Flow.js.map
