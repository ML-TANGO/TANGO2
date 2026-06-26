import React, { useCallback, useEffect, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import {
  adoptPromptCandidate,
  discardPromptCandidate,
  getPromptCandidates,
  getSynthesisProject,
  regeneratePromptCandidates,
} from '@src/apis/flightbase/synthesis';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisPromptOptimizeContent.module.scss';

const cx = classNames.bind(style);

export default function UserSynthesisPromptOptimizeContent() {
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [project, setProject] = useState(null);
  const [data, setData] = useState({
    candidates: [],
    method: 'OPRO',
    iteration: 0,
    adopted_prompt: null,
    mock: false,
  });

  const fetchProject = useCallback(async () => {
    const { result, status } = await getSynthesisProject(projectId);
    if (status === STATUS_SUCCESS) setProject(result);
  }, [projectId]);

  const fetchCandidates = useCallback(async () => {
    const { result, status, message } = await getPromptCandidates(projectId);
    if (status === STATUS_SUCCESS) setData(result);
    else toast.error(message);
  }, [projectId]);

  useEffect(() => {
    fetchProject();
    fetchCandidates();
  }, [fetchProject, fetchCandidates]);

  if (!project) return <div className={cx('cont')}>불러오는 중...</div>;

  const handleRegenerate = async () => {
    const { status, message } = await regeneratePromptCandidates(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success('후보를 재생성했습니다.');
      fetchProject();
      fetchCandidates();
    } else {
      toast.error(message);
    }
  };

  const handleAdopt = async (c) => {
    const { status, message } = await adoptPromptCandidate(projectId, c.id);
    if (status === STATUS_SUCCESS) {
      toast.success('프롬프트를 채택했습니다.');
      fetchProject();
      fetchCandidates();
    } else {
      toast.error(message);
    }
  };

  const handleDiscard = async (c) => {
    const { status, message } = await discardPromptCandidate(projectId, c.id);
    if (status === STATUS_SUCCESS) fetchCandidates();
    else toast.error(message);
  };

  const visible = (data.candidates || []).filter((c) => c.status !== 'discarded');

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
      <h1 className={cx('title')}>프롬프트 최적화 — LLM1</h1>
      <p className={cx('desc')}>
        메타프롬프트로부터 최적 프롬프트/인스트럭션을 생성합니다. (방식:{' '}
        {data.method} · iteration {data.iteration}){' '}
        {data.mock && (
          <span className={cx('mock')}>[mock — 고려대 LLM1 수령 시 교체]</span>
        )}
      </p>

      <div className={cx('meta-box')}>
        <b>메타프롬프트</b>
        <div>{project.params?.meta_prompt || '-'}</div>
        {data.adopted_prompt && (
          <div className={cx('adopted')}>✓ 채택됨: {data.adopted_prompt}</div>
        )}
      </div>

      <div className={cx('run-row')}>
        <ButtonV2
          colorType='blue'
          label='🔁 최적화 실행'
          onClick={handleRegenerate}
        />
        <ButtonV2
          type='outline'
          label='📋 후보 전체 목록'
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-list`,
            )
          }
        />
      </div>

      <h2 className={cx('sub')}>생성된 프롬프트 후보 (점수순)</h2>
      <div className={cx('candidates')}>
        {visible.length === 0 && (
          <div className={cx('empty')}>
            후보가 없습니다. “최적화 실행”을 누르세요.
          </div>
        )}
        {visible.map((c) => (
          <div key={c.id} className={cx('cand')}>
            <div className={cx('score')}>{c.score}</div>
            <div className={cx('prompt')}>{c.prompt}</div>
            <div className={cx('cand-actions')}>
              {c.status === 'adopted' ? (
                <span className={cx('adopted-tag')}>✓ 채택됨</span>
              ) : (
                <>
                  <ButtonV2
                    colorType='skyblue'
                    label='✓ 채택'
                    onClick={() => handleAdopt(c)}
                  />
                  <ButtonV2
                    type='outline'
                    label='폐기'
                    onClick={() => handleDiscard(c)}
                  />
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
