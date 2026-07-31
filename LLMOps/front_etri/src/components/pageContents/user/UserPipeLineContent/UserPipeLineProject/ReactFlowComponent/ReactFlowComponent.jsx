import React, { useCallback, useEffect, useState } from 'react';

import {
  Controls,
  MarkerType,
  MiniMap,
  PanOnScrollMode,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';

import '@xyflow/react/dist/style.css';

import ColorSelectorNode from '../ColorSelectorNode';

import './ReactFlowComponent.scss';

import { shallowEqual, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import _ from 'lodash';

import {
  putPipelinesGraph,
  putPipelinesTask,
} from '@src/apis/flightbase/pipeline';

import EmptyContent from '../EmptyContent';
import LineContent from '../LineContent';
import NodeHeader from '../NodeHeader';

import {
  calBorderAnimate,
  calDeloymentGroupList,
  calHeight,
  calLastPosition,
  calLineColor,
  calListHeaderGroup,
  calNodeDataList,
  calPreDataGroupList,
  calSwapArrayCoordinate,
  calTrainGroupList,
  nodeLineColorStyle,
  xPositionList,
} from './util';

const connectionLineStyle = { stroke: '#000' };

const nodeTypes = {
  nodeHeader: NodeHeader,
  emptyGroup: EmptyContent,
  lineGroup: LineContent,
  node: ColorSelectorNode,
};

const ReactFlowComponent = ({
  pipelineType,
  handleResetData,
  isStopBtn,
  dataset_info,
}) => {
  const { preprocessing_task, project_task, deployment_task } = useSelector(
    (state) => state.pipelineList,
    shallowEqual,
  );

  const match = useRouteMatch();
  const { params } = match;
  const { tid: pipelineId } = params;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    const preDataHeaderGroup = calListHeaderGroup(
      0,
      '학습 데이터 전처리',
      isStopBtn,
    );
    const preDataGroupList = calPreDataGroupList(
      preprocessing_task,
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const preDataGroupLastValue = _.last(preDataGroupList);

    const trainStartPositionY = calLastPosition(preDataGroupLastValue);
    const trainListHeaderGroup = calListHeaderGroup(
      trainStartPositionY,
      '학습',
      isStopBtn,
    );
    const trainGroupList = calTrainGroupList(
      project_task,
      handleResetData,
      trainStartPositionY,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const tarinGroupLastValue = _.last(trainGroupList);

    const deploymentPositionY = calLastPosition(tarinGroupLastValue);
    const deplopmentListHeaderGroup = calListHeaderGroup(
      deploymentPositionY,
      '배포',
      isStopBtn,
    );
    const deploymentGroupList = calDeloymentGroupList(
      deployment_task,
      handleResetData,
      deploymentPositionY,
      isStopBtn,
      dataset_info,
      pipelineType,
    );

    const preDataListNodeList = calNodeDataList(
      preprocessing_task,
      'pre-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const trainDataListNodeList = calNodeDataList(
      project_task,
      'train-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const deploymentNodeList = calNodeDataList(
      deployment_task,
      'deployment-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );

    const maxHeight = calHeight(deploymentGroupList);

    const totalPreNodeList = [
      preDataHeaderGroup,
      trainListHeaderGroup,
      deplopmentListHeaderGroup,
      ...preDataGroupList,
      ...preDataListNodeList,
      ...trainGroupList,
      ...trainDataListNodeList,
      ...deploymentGroupList,
      ...deploymentNodeList,
    ];

    const nodeList = [
      ...preDataListNodeList,
      ...trainDataListNodeList,
      ...deploymentNodeList,
    ];

    const edgeList = [];

    nodeList.forEach((info) => {
      const { task_type, status } = info.data;
      const borderColor = calLineColor(isStopBtn, status, task_type);
      const isAnimated = calBorderAnimate(status, isStopBtn);
      info.data.successors.forEach((id) => {
        edgeList.push({
          id: `xy-edge__${info.id}-${id}`,
          source: info.id,
          target: id,
          animated: isAnimated,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 30,
            height: 30,
            color: borderColor,
          },
          style: { stroke: borderColor, zIndex: 600 },
        });
      });
    });

    setHeight(maxHeight);
    setNodes(totalPreNodeList);
    setEdges(edgeList);
  }, [
    preprocessing_task,
    deployment_task,
    handleResetData,
    isStopBtn,
    project_task,
    setEdges,
    setNodes,
    dataset_info,
    pipelineType,
  ]);

  const onConnect = useCallback(
    async (params) => {
      if (isStopBtn) return;
      if (pipelineType === 'built-in') return;

      const { sourceHandle, source, target, targetHandle } = params;
      const splitSource = sourceHandle.split('-');
      const splitTarget = targetHandle.split('-');

      const sourceType = splitSource[0];
      const targetType = splitTarget[0];

      const sourceY = splitSource[1];
      const targetY = splitTarget[1];

      if (source === target) return;
      if (sourceY === targetY && sourceType === targetType) return;

      const sourceNode = nodes.find((el) => el.id === source);
      const targetNode = nodes.find((el) => el.id === target);

      if (sourceNode.data.successors.includes(target)) return;

      await putPipelinesGraph({
        pipeline_id: +pipelineId,
        predecessor_task: {
          id: +source,
          predecessors: sourceNode.data.predecessors,
          successors: [...sourceNode.data.successors, target],
        },
        successor_task: {
          id: +target,
          predecessors: [...targetNode.data.predecessors, source],
          successors: targetNode.data.successors,
        },
      });
      await handleResetData();
    },
    [handleResetData, isStopBtn, nodes, pipelineId, pipelineType],
  );

  const calFindClosestValue = (arr, target) => {
    let closestValue = arr[0];
    let smallestDifference = Math.abs(target - arr[0]);
    let index = 0;

    for (let i = 1; i < arr.length; i++) {
      const difference = Math.abs(target - arr[i]);
      if (difference < smallestDifference) {
        smallestDifference = difference;
        closestValue = arr[i];
        index = i;
      }
    }

    return {
      xPosition: closestValue,
      index,
    };
  };

  // 노드 드래그 종료 후 핸들러
  const handleNodeDragStop = async (event, selectedNode) => {
    const transformNode = nodes.slice();

    // ** 선택된 노드 **
    const { x: selectedNodeX } = selectedNode.position;
    const closetValue = calFindClosestValue(xPositionList, selectedNodeX);

    const findRowGroupNodeList = nodes.filter(
      (info) => info.parentId === selectedNode.parentId,
    );

    const isXpositionValue = findRowGroupNodeList.find(
      (info) => info.data.coordinate.x_index === closetValue.index,
    );
    const findSelectedNode = transformNode.find(
      (el) => el.id === selectedNode.id,
    );

    if (
      isXpositionValue &&
      closetValue.index !== selectedNode.data.coordinate.x_index
    ) {
      const findSelectedNodeIndex = nodes.findIndex((info) => {
        return info.id === selectedNode.id;
      });
      const changedIndex = nodes.findIndex(
        (el) => el.id === isXpositionValue.id,
      );

      const newArr = calSwapArrayCoordinate(
        nodes,
        findSelectedNodeIndex,
        changedIndex,
      );

      const changeData1 = newArr[findSelectedNodeIndex];
      const changeData2 = newArr[changedIndex];

      const tasks = [
        await putPipelinesTask({
          x_position: 0,
          x_index: changeData1.data.coordinate.x_index,
          y_index: changeData1.data.coordinate.y_index,
          task_id: changeData1.data.id,
        }),

        await putPipelinesTask({
          x_position: 0,
          x_index: changeData2.data.coordinate.x_index,
          y_index: changeData2.data.coordinate.y_index,
          task_id: changeData2.data.id,
        }),
      ];

      await Promise.all(tasks);
      await handleResetData();
    } else {
      if (closetValue.index === findSelectedNode.data.coordinate.x_index) {
        handleResetData();
        return;
      }

      findSelectedNode.data.coordinate.x_index = closetValue.index;
      findSelectedNode.position.x = closetValue.xPosition;
      const { data } = findSelectedNode;

      await putPipelinesTask({
        x_position: 0,
        x_index: closetValue.index,
        y_index: data.coordinate.y_index,
        task_id: +findSelectedNode.id,
      });
      await handleResetData();
    }
  };

  return (
    <div
      id='flow-container'
      style={{
        width: '100%',
        height: `${height + 390}px`,
        position: 'relative',
      }}
      className='nopan'
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={handleNodeDragStop}
        nodeTypes={nodeTypes}
        nodesDraggable={!isStopBtn && pipelineType !== 'built-in'}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        panOnScrollMode={PanOnScrollMode.Vertical}
        panOnScroll={false}
        autoPanOnNodeDrag={false}
        autoPanOnConnect={false}
        preventScrolling={false}
        connectionLineStyle={connectionLineStyle}
        style={{
          background: '#fbfcff',
          width: '100%',
          maxHeight: '100%',
        }}
      >
        <MiniMap
          nodeColor={(n) => {
            if (n.type === 'node') return '#fbfcff';
            return '#fff';
          }}
          nodeStrokeColor={(nodeInfo) => {
            return nodeLineColorStyle[nodeInfo.data.task_type];
          }}
        />
        <Controls />
      </ReactFlow>
    </div>
  );
};

export default ReactFlowComponent;
