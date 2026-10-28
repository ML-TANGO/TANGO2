import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  {
    key: 'LLM1',
    labelKey: 'synthesis.module.llm1.label',
    descKey: 'synthesis.canvas.module.llm1.desc',
  },
  {
    key: 'LLM2',
    labelKey: 'synthesis.module.llm2.label',
    descKey: 'synthesis.canvas.module.llm2.desc',
  },
  {
    key: 'LLM3',
    labelKey: 'synthesis.module.llm3.label',
    descKey: 'synthesis.canvas.module.llm3.desc',
  },
];

const STATUS_KEYS = {
  created: 'synthesis.status.created',
  running: 'synthesis.status.running',
  completed: 'synthesis.status.completed',
  failed: 'synthesis.status.failed',
  cancelled: 'synthesis.status.cancelled',
};

const statusLabel = (t, s) => (STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s || '-');

export default function UserSynthesisCanvasContent() {
  const { t } = useTranslation();
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
          <div className={cx('node-label')}>{t(m.labelKey)}</div>
          <div className={cx('node-desc')}>{t(m.descKey)}</div>
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
        className={cx('back-to-list')}
        onClick={() =>
          history.push(
            `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/overview`,
          )
        }
      >
        <img
          className={cx('back-btn-image')}
          src='/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='<'
        />
        <span className={cx('back-btn-label')}>
          {t('synthesis.overview.label')}
        </span>
      </button>
      <div className={cx('head')}>
        <h1 className={cx('title')}>
          {t('synthesis.canvas.title', { name: project?.name || '' })}
        </h1>
        <span className={cx('status', project?.status)}>
          {statusLabel(t, project?.status)}
        </span>
        <ButtonV2
          type='outline'
          label={t('synthesis.action.wizard')}
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/wizard`,
            )
          }
        />
      </div>
      <p className={cx('desc')}>{t('synthesis.canvas.desc')}</p>
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
