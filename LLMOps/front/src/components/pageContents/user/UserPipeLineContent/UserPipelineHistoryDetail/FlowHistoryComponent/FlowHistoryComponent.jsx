import React, { useCallback, useEffect, useState } from 'react';
import { shallowEqual, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import {
  Controls,
  MarkerType,
  MiniMap,
  PanOnScrollMode,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import _ from 'lodash';

import {
  putPipelinesGraph,
  putPipelinesTask,
} from '@src/apis/flightbase/pipeline';

import ColorSelectorNode from '../../UserPipeLineProject/ColorSelectorNode';
import EmptyContent from '../../UserPipeLineProject/EmptyContent';
import LineContent from '../../UserPipeLineProject/LineContent';
import NodeHeader from '../../UserPipeLineProject/NodeHeader';

import {
  calFinetuningGroupList,
  calGenerationGroupList,
  calHeight,
  calLastPosition,
  calLineColor,
  calListHeaderGroup,
  calLlmDeployGroupList,
  calNodeDataList,
  calPreDataGroupList,
  calQuantizeGroupList,
  calSwapArrayCoordinate,
  nodeLineColorStyle,
  xPositionList,
} from '../../UserPipeLineProject/ReactFlowComponent/util';

import classNames from 'classnames/bind';
import style from './FlowHistoryComponent.module.scss';

const cx = classNames.bind(style);

const connectionLineStyle = { stroke: '#000' };

const nodeTypes = {
  nodeHeader: NodeHeader,
  emptyGroup: EmptyContent,
  lineGroup: LineContent,
  node: ColorSelectorNode,
};

const FlowHistoryComponent = ({ handleResetData, isStopBtn = true }) => {
  const {
    generation_task,
    preprocessing_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
  } = useSelector((state) => state.pipelineList, shallowEqual);

  const match = useRouteMatch();
  const { params } = match;
  const { tid: pipelineId } = params;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    // 라이브 캔버스(ReactFlowComponent)와 동일 GenAI 레인셋 미러(읽기전용):
    // 생성 → 전처리 → 파인튜닝 → 양자화 → LLM배포. (dataset_info/pipelineType=undefined: 히스토리=비편집)
    const generationHeaderGroup = calListHeaderGroup(0, '생성 데이터', isStopBtn);
    const generationGroupList = calGenerationGroupList(
      generation_task,
      handleResetData,
      isStopBtn,
      undefined,
      undefined,
      0,
    );
    const generationGroupLastValue = _.last(generationGroupList);

    const preDataStartPositionY = calLastPosition(generationGroupLastValue);
    const preDataHeaderGroup = calListHeaderGroup(
      preDataStartPositionY,
      '학습 데이터 전처리',
      isStopBtn,
    );
    const preDataGroupList = calPreDataGroupList(
      preprocessing_task,
      handleResetData,
      isStopBtn,
      undefined,
      undefined,
      preDataStartPositionY,
    );
    const preDataGroupLastValue = _.last(preDataGroupList);

    const finetuneStartPositionY = calLastPosition(preDataGroupLastValue);
    const finetuneHeaderGroup = calListHeaderGroup(
      finetuneStartPositionY,
      '파인튜닝',
      isStopBtn,
    );
    const finetuneGroupList = calFinetuningGroupList(
      finetuning_task,
      handleResetData,
      isStopBtn,
      undefined,
      undefined,
      finetuneStartPositionY,
    );
    const finetuneGroupLastValue = _.last(finetuneGroupList);

    const quantizeStartPositionY = calLastPosition(finetuneGroupLastValue);
    const quantizeHeaderGroup = calListHeaderGroup(
      quantizeStartPositionY,
      '양자화',
      isStopBtn,
    );
    const quantizeGroupList = calQuantizeGroupList(
      quantize_task,
      handleResetData,
      isStopBtn,
      undefined,
      undefined,
      quantizeStartPositionY,
    );
    const quantizeGroupLastValue = _.last(quantizeGroupList);

    const llmDeployPositionY = calLastPosition(quantizeGroupLastValue);
    const llmDeployHeaderGroup = calListHeaderGroup(
      llmDeployPositionY,
      'LLM 배포',
      isStopBtn,
    );
    const llmDeployGroupList = calLlmDeployGroupList(
      llm_deploy_task,
      handleResetData,
      isStopBtn,
      undefined,
      undefined,
      llmDeployPositionY,
    );

    const generationNodeList = calNodeDataList(
      generation_task,
      'generation-group',
      handleResetData,
      isStopBtn,
    );
    const preDataListNodeList = calNodeDataList(
      preprocessing_task,
      'pre-group',
      handleResetData,
      isStopBtn,
    );
    const finetuneNodeList = calNodeDataList(
      finetuning_task,
      'finetuning-group',
      handleResetData,
      isStopBtn,
    );
    const quantizeNodeList = calNodeDataList(
      quantize_task,
      'quantize-group',
      handleResetData,
      isStopBtn,
    );
    const llmDeployNodeList = calNodeDataList(
      llm_deploy_task,
      'llm-deploy-group',
      handleResetData,
      isStopBtn,
    );

    const maxHeight = calHeight(llmDeployGroupList);

    const totalPreNodeList = [
      generationHeaderGroup,
      preDataHeaderGroup,
      finetuneHeaderGroup,
      quantizeHeaderGroup,
      llmDeployHeaderGroup,
      ...generationGroupList,
      ...generationNodeList,
      ...preDataGroupList,
      ...preDataListNodeList,
      ...finetuneGroupList,
      ...finetuneNodeList,
      ...quantizeGroupList,
      ...quantizeNodeList,
      ...llmDeployGroupList,
      ...llmDeployNodeList,
    ];

    const nodeList = [
      ...generationNodeList,
      ...preDataListNodeList,
      ...finetuneNodeList,
      ...quantizeNodeList,
      ...llmDeployNodeList,
    ];

    const edgeList = [];

    nodeList.forEach((info) => {
      const { task_type, status } = info.data;
      const borderColor = calLineColor(isStopBtn, status, task_type);
      info.data.successors.forEach((id) => {
        edgeList.push({
          id: `xy-edge__${info.id}-${id}`,
          source: info.id,
          target: id,
          animated: false,
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
    generation_task,
    preprocessing_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
    handleResetData,
    isStopBtn,
    setEdges,
    setNodes,
  ]);

  const onConnect = useCallback(
    async (params) => {
      if (isStopBtn) return;

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
    [handleResetData, isStopBtn, nodes, pipelineId],
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
        nodesDraggable={!isStopBtn}
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
          background: '#fff',
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

export default FlowHistoryComponent;
