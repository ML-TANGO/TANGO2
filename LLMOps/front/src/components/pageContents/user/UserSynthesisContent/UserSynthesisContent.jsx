import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import {
  deleteSynthesisProject,
  getSynthesisProjects,
  runSynthesis,
} from '@src/apis/flightbase/synthesis';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisContent.module.scss';

const cx = classNames.bind(style);

const STATUS_KEYS = {
  created: 'synthesis.status.created',
  running: 'synthesis.status.running',
  completed: 'synthesis.status.completed',
  failed: 'synthesis.status.failed',
  cancelled: 'synthesis.status.cancelled',
};

const statusLabel = (t, s) => (STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s || '-');

export default function UserSynthesisContent() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [projects, setProjects] = useState([]);
  const loading = useRef(false);

  const fetchProjects = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const { result, status, message } =
        await getSynthesisProjects(workspaceId);
      if (status === STATUS_SUCCESS) setProjects(result || []);
      else toast.error(message);
    } finally {
      loading.current = false;
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // 실행 중 프로젝트가 있으면 폴링
  useEffect(() => {
    const running = projects.some((p) => p.status === 'running');
    if (!running) return undefined;
    const iv = setInterval(fetchProjects, 3000);
    return () => clearInterval(iv);
  }, [projects, fetchProjects]);

  const handleCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_SYNTHESIS_PROJECT',
        modalData: { workspaceId, handleResetData: fetchProjects },
      }),
    );
  };

  const handleRun = async (id) => {
    const { status, message } = await runSynthesis(id);
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.runStarted'));
      fetchProjects();
    } else {
      toast.error(message);
    }
  };

  const handleDelete = async (id) => {
    const { status, message } = await deleteSynthesisProject(id);
    if (status === STATUS_SUCCESS) fetchProjects();
    else toast.error(message);
  };

  return (
    <div className={cx('cont')}>
      <div className={cx('header')}>
        <h1 className={cx('title')}>{t('synthesis.label')}</h1>
        <ButtonV2
          colorType='blue'
          label={t('synthesis.project.create')}
          onClick={handleCreate}
        />
      </div>
      <p className={cx('desc')}>{t('synthesis.desc')}</p>

      <div className={cx('list')}>
        {projects.length === 0 && (
          <div className={cx('empty')}>{t('synthesis.empty')}</div>
        )}
        {projects.map((p) => (
          <div
            key={p.id}
            className={cx('card', 'clickable', p.status)}
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${p.id}/overview`,
              )
            }
          >
            <div className={cx('card-head')}>
              <span className={cx('field')}>{p.field || '-'}</span>
              <span className={cx('status', p.status)}>
                {statusLabel(t, p.status)}
              </span>
            </div>
            <div className={cx('name')}>{p.name}</div>
            <div className={cx('meta')}>
              <span>
                {t('synthesis.card.module', {
                  name: p.manifest_name,
                  version: p.manifest_version,
                })}
              </span>
              <span>
                {t('synthesis.card.resultCount', { n: p.result_count || 0 })}
              </span>
            </div>
            <div className={cx('actions')} onClick={(e) => e.stopPropagation()}>
              <ButtonV2
                colorType='skyblue'
                label={t('run.label')}
                onClick={() => handleRun(p.id)}
                disabled={p.status === 'running'}
              />
              <ButtonV2
                type='outline'
                label={t('delete.label')}
                onClick={() => handleDelete(p.id)}
                disabled={p.status === 'running'}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
