import React, { useEffect, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ButtonV2 } from '@jonathan/ui-react';

import { getSynthesisProject } from '@src/apis/flightbase/synthesis';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisCanvasContent.module.scss';

const cx = classNames.bind(style);

const MODULES = [
  { key: 'LLM1', label: '프롬프트 생성기', desc: '메타프롬프트 → 프롬프트/인스트럭션' },
  { key: 'LLM2', label: '데이터 생성기', desc: '프롬프트 → 데이터 라벨' },
  { key: 'LLM3', label: '알고리즘 호출자', desc: 'API Call → 학습 알고리즘' },
];

const statusLabel = (s) =>
  ({ created: '대기', running: '실행 중', completed: '완료', failed: '실패', cancelled: '취소' }[s] ||
    s ||
    '-');

export default function UserSynthesisCanvasContent() {
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;
  const [project, setProject] = useState(null);

  useEffect(() => {
    (async () => {
      const { result, status } = await getSynthesisProject(projectId);
      if (status === STATUS_SUCCESS) setProject(result);
    })();
  }, [projectId]);

  const running = project?.status === 'running';

  const nodes = MODULES.map((m, i) => ({
    id: m.key,
    position: { x: i * 280, y: 60 },
    data: {
      label: (
        <div className={cx('node')}>
          <div className={cx('node-key')}>{m.key}</div>
          <div className={cx('node-label')}>{m.label}</div>
          <div className={cx('node-desc')}>{m.desc}</div>
        </div>
      ),
    },
    style: {
      width: 220,
      border: `2px solid ${i === 1 ? '#8B5CF6' : '#e5e7eb'}`,
      borderRadius: 12,
      padding: 8,
    },
  }));

  const edges = [
    { id: 'e1', source: 'LLM1', target: 'LLM2', animated: running },
    { id: 'e2', source: 'LLM2', target: 'LLM3', animated: running },
  ];

  return (
    <div className={cx('cont')}>
      <button
        className={cx('back')}
        onClick={() =>
          history.push(
            `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/overview`,
          )
        }
      >
        ← 개요
      </button>
      <div className={cx('head')}>
        <h1 className={cx('title')}>캔버스 — {project?.name || ''}</h1>
        <span className={cx('status', project?.status)}>
          {statusLabel(project?.status)}
        </span>
        <ButtonV2
          type='outline'
          label='🧭 마법사'
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/wizard`,
            )
          }
        />
      </div>
      <p className={cx('desc')}>
        3-모듈 오케스트레이션 캔버스 뷰(고급). 마법사와 같은 합성 프로젝트의 자유편집 뷰.
      </p>
      <div className={cx('canvas')}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
