import React, { useCallback, useEffect, useRef, useState } from 'react';
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

const statusLabel = (s) =>
  ({
    created: '대기',
    running: '실행 중',
    completed: '완료',
    failed: '실패',
    cancelled: '취소',
  }[s] || s || '-');

export default function UserSynthesisContent() {
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
      const { result, status, message } = await getSynthesisProjects(workspaceId);
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
      toast.success('생성 실행을 시작했습니다.');
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
        <h1 className={cx('title')}>합성 데이터 생성</h1>
        <ButtonV2
          colorType='blue'
          label='+ 합성 프로젝트 생성'
          onClick={handleCreate}
        />
      </div>
      <p className={cx('desc')}>
        3-모듈 오케스트레이션(LLM1 프롬프트 생성 → LLM2 데이터 생성 → LLM3 알고리즘
        호출)으로 도메인 특화 인스트럭션 데이터를 합성합니다.
      </p>

      <div className={cx('list')}>
        {projects.length === 0 && (
          <div className={cx('empty')}>
            합성 프로젝트가 없습니다. “합성 프로젝트 생성”으로 시작하세요.
          </div>
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
                {statusLabel(p.status)}
              </span>
            </div>
            <div className={cx('name')}>{p.name}</div>
            <div className={cx('meta')}>
              <span>
                모듈: {p.manifest_name} ({p.manifest_version})
              </span>
              <span>생성 데이터: {p.result_count || 0}건</span>
            </div>
            <div
              className={cx('actions')}
              onClick={(e) => e.stopPropagation()}
            >
              <ButtonV2
                colorType='skyblue'
                label='실행'
                onClick={() => handleRun(p.id)}
                disabled={p.status === 'running'}
              />
              <ButtonV2
                type='outline'
                label='삭제'
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
