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
  calFinetuningGroupList,
  calGenerationGroupList,
  calHeight,
  calLastPosition,
  calLineColor,
  calListHeaderGroup,
  calLlmDeployGroupList,
  calModuleGroupList,
  calNodeDataList,
  calPreDataGroupList,
  calQuantizeGroupList,
  calSwapArrayCoordinate,
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
  const {
    generation_task,
    preprocessing_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
    prompt_gen_task,
    data_gen_task,
    algo_call_task,
  } = useSelector((state) => state.pipelineList, shallowEqual);

  const match = useRouteMatch();
  const { params } = match;
  const { tid: pipelineId } = params;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    // 생성 레인 (캔버스 맨 앞, y=0). dataset → 생성 → 전처리 → 학습 → 배포. (WBS 1.2)
    const generationHeaderGroup = calListHeaderGroup(0, '생성 데이터', isStopBtn);
    const generationGroupList = calGenerationGroupList(
      generation_task,
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
      0,
    );
    const generationGroupLastValue = _.last(generationGroupList);

    // 전처리 레인 — 생성 레인 다음으로 offset (캐스케이드).
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
      dataset_info,
      pipelineType,
      preDataStartPositionY,
    );
    const preDataGroupLastValue = _.last(preDataGroupList);

    // SP-7 프롬프트 최적화 3-모듈 레인 (전처리 다음, 파인튜닝 앞 — 명령 데이터셋 생성 흐름).
    // LLM1 프롬프트 생성 → LLM2 데이터 생성 → LLM3 알고리즘 호출. 전부 external_container
    // manifest 노드(고려대 컨테이너). (SP-7 Phase 2 scaffolding, v0.4 3.3/3.5)
    const promptGenStartPositionY = calLastPosition(preDataGroupLastValue);
    const promptGenHeaderGroup = calListHeaderGroup(
      promptGenStartPositionY,
      '프롬프트 생성',
      isStopBtn,
    );
    const promptGenGroupList = calModuleGroupList(
      prompt_gen_task,
      'promptgen',
      'prompt-gen-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
      promptGenStartPositionY,
    );
    const promptGenGroupLastValue = _.last(promptGenGroupList);

    const dataGenStartPositionY = calLastPosition(promptGenGroupLastValue);
    const dataGenHeaderGroup = calListHeaderGroup(
      dataGenStartPositionY,
      '데이터 생성',
      isStopBtn,
    );
    const dataGenGroupList = calModuleGroupList(
      data_gen_task,
      'datagen',
      'data-gen-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
      dataGenStartPositionY,
    );
    const dataGenGroupLastValue = _.last(dataGenGroupList);

    const algoCallStartPositionY = calLastPosition(dataGenGroupLastValue);
    const algoCallHeaderGroup = calListHeaderGroup(
      algoCallStartPositionY,
      '알고리즘 호출',
      isStopBtn,
    );
    const algoCallGroupList = calModuleGroupList(
      algo_call_task,
      'algocall',
      'algo-call-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
      algoCallStartPositionY,
    );
    const algoCallGroupLastValue = _.last(algoCallGroupList);

    // 파인튜닝 레인 — SP-7 알고리즘 호출 다음(캐스케이드). 데이터셋 → 생성 → 전처리 →
    // (SP-7 프롬프트생성 → 데이터생성 → 알고리즘호출) → 파인튜닝 → 양자화 → LLM배포.
    // (GenAI 통합 파이프라인 최종 레인셋. ML/DL project/deployment 는 코드/버킷 보존하되 렌더 제외)
    const finetuneStartPositionY = calLastPosition(algoCallGroupLastValue);
    const finetuneHeaderGroup = calListHeaderGroup(
      finetuneStartPositionY,
      '파인튜닝',
      isStopBtn,
    );
    const finetuneGroupList = calFinetuningGroupList(
      finetuning_task,
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
      finetuneStartPositionY,
    );
    const finetuneGroupLastValue = _.last(finetuneGroupList);

    // 양자화 레인 — 파인튜닝 다음(캐스케이드, 엣지 배포 전제 GGUF·선택 노드).
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
      dataset_info,
      pipelineType,
      quantizeStartPositionY,
    );
    const quantizeGroupLastValue = _.last(quantizeGroupList);

    // LLM 배포 레인 — 양자화 다음(터미널 레인). 타겟=클러스터(Playground)/엣지(SP-6).
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
      dataset_info,
      pipelineType,
      llmDeployPositionY,
    );

    const generationNodeList = calNodeDataList(
      generation_task,
      'generation-group',
      handleResetData,
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
    const promptGenNodeList = calNodeDataList(
      prompt_gen_task,
      'prompt-gen-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const dataGenNodeList = calNodeDataList(
      data_gen_task,
      'data-gen-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const algoCallNodeList = calNodeDataList(
      algo_call_task,
      'algo-call-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const finetuneNodeList = calNodeDataList(
      finetuning_task,
      'finetuning-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const quantizeNodeList = calNodeDataList(
      quantize_task,
      'quantize-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );
    const llmDeployNodeList = calNodeDataList(
      llm_deploy_task,
      'llm-deploy-group',
      handleResetData,
      isStopBtn,
      dataset_info,
      pipelineType,
    );

    const maxHeight = calHeight(llmDeployGroupList);

    const totalPreNodeList = [
      generationHeaderGroup,
      preDataHeaderGroup,
      promptGenHeaderGroup,
      dataGenHeaderGroup,
      algoCallHeaderGroup,
      finetuneHeaderGroup,
      quantizeHeaderGroup,
      llmDeployHeaderGroup,
      ...generationGroupList,
      ...generationNodeList,
      ...preDataGroupList,
      ...preDataListNodeList,
      ...promptGenGroupList,
      ...promptGenNodeList,
      ...dataGenGroupList,
      ...dataGenNodeList,
      ...algoCallGroupList,
      ...algoCallNodeList,
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
      ...promptGenNodeList,
      ...dataGenNodeList,
      ...algoCallNodeList,
      ...finetuneNodeList,
      ...quantizeNodeList,
      ...llmDeployNodeList,
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
    generation_task,
    preprocessing_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
    prompt_gen_task,
    data_gen_task,
    algo_call_task,
    handleResetData,
    isStopBtn,
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
