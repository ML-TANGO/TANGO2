import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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

  if (!project)
    return <div className={cx('cont')}>{t('synthesis.loading')}</div>;

  const handleRegenerate = async () => {
    const { status, message } = await regeneratePromptCandidates(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.candidatesRegenerated'));
      fetchProject();
      fetchCandidates();
    } else {
      toast.error(message);
    }
  };

  const handleAdopt = async (c) => {
    const { status, message } = await adoptPromptCandidate(projectId, c.id);
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.promptAdopted'));
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

  const visible = (data.candidates || []).filter(
    (c) => c.status !== 'discarded',
  );

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
      <h1 className={cx('title')}>{t('synthesis.promptOptimize.title')}</h1>
      <p className={cx('desc')}>
        {t('synthesis.promptOptimize.desc', {
          method: data.method,
          iteration: data.iteration,
        })}{' '}
        {data.mock && (
          <span className={cx('mock')}>
            {t('synthesis.promptOptimize.mockNote')}
          </span>
        )}
      </p>

      <div className={cx('meta-box')}>
        <b>{t('synthesis.info.metaPrompt')}</b>
        <div>{project.params?.meta_prompt || '-'}</div>
        {data.adopted_prompt && (
          <div className={cx('adopted')}>
            {t('synthesis.prompt.adopted', { prompt: data.adopted_prompt })}
          </div>
        )}
      </div>

      <div className={cx('run-row')}>
        <ButtonV2
          colorType='blue'
          label={t('synthesis.action.runOptimize')}
          onClick={handleRegenerate}
        />
        <ButtonV2
          type='outline'
          label={t('synthesis.action.allCandidates')}
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-list`,
            )
          }
        />
      </div>

      <h2 className={cx('sub')}>
        {t('synthesis.promptOptimize.candidatesTitle')}
      </h2>
      <div className={cx('candidates')}>
        {visible.length === 0 && (
          <div className={cx('empty')}>
            {t('synthesis.promptOptimize.empty')}
          </div>
        )}
        {visible.map((c) => (
          <div key={c.id} className={cx('cand')}>
            <div className={cx('score')}>{c.score}</div>
            <div className={cx('prompt')}>{c.prompt}</div>
            <div className={cx('cand-actions')}>
              {c.status === 'adopted' ? (
                <span className={cx('adopted-tag')}>
                  {t('synthesis.prompt.adoptedTag')}
                </span>
              ) : (
                <>
                  <ButtonV2
                    colorType='skyblue'
                    label={t('synthesis.action.adopt')}
                    onClick={() => handleAdopt(c)}
                  />
                  <ButtonV2
                    type='outline'
                    label={t('synthesis.action.discard')}
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
