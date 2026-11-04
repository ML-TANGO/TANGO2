import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import {
  getPromptCandidates,
  getSynthesisProject,
  getSynthesisResult,
  runSynthesis,
  updateSynthesisProject,
} from '@src/apis/flightbase/synthesis';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisWizardContent.module.scss';

const cx = classNames.bind(style);

const STEPS = [
  {
    labelKey: 'synthesis.wizard.step1.label',
    subKey: 'synthesis.wizard.step1.sub',
  },
  {
    labelKey: 'synthesis.wizard.step2.label',
    subKey: 'synthesis.wizard.step2.sub',
  },
  {
    labelKey: 'synthesis.wizard.step3.label',
    subKey: 'synthesis.wizard.step3.sub',
  },
  {
    labelKey: 'synthesis.wizard.step4.label',
    subKey: 'synthesis.wizard.step4.sub',
  },
  {
    labelKey: 'synthesis.wizard.step5.label',
    subKey: 'synthesis.wizard.step5.sub',
  },
  {
    labelKey: 'synthesis.wizard.step6.label',
    subKey: 'synthesis.wizard.step6.sub',
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

export default function UserSynthesisWizardContent() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [step, setStep] = useState(0);
  const [project, setProject] = useState(null);
  const [cand, setCand] = useState({
    candidates: [],
    method: 'OPRO',
    adopted_prompt: null,
    mock: false,
  });
  const [discarded, setDiscarded] = useState([]);
  const [result, setResult] = useState({ records: [], total: 0 });
  const loading = useRef(false);

  const fetchProject = useCallback(async () => {
    const { result: p, status } = await getSynthesisProject(projectId);
    if (status === STATUS_SUCCESS) setProject(p);
  }, [projectId]);

  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  useEffect(() => {
    if (step === 1) {
      getPromptCandidates(projectId).then(({ result, status }) => {
        if (status === STATUS_SUCCESS) {
          setCand(result);
          setDiscarded([]);
        }
      });
    }
    if (step === 2) {
      getSynthesisResult(projectId).then(({ result, status }) => {
        if (status === STATUS_SUCCESS && result) setResult(result);
      });
    }
  }, [step, projectId]);

  // step 2 실행 중 폴링
  useEffect(() => {
    if (step !== 2 || project?.status !== 'running') return undefined;
    const iv = setInterval(async () => {
      if (loading.current) return;
      loading.current = true;
      try {
        await fetchProject();
        const { result, status } = await getSynthesisResult(projectId);
        if (status === STATUS_SUCCESS && result) setResult(result);
      } finally {
        loading.current = false;
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [step, project, projectId, fetchProject]);

  if (!project)
    return <div className={cx('cont')}>{t('synthesis.loading')}</div>;

  const handleEdit = () =>
    dispatch(
      openModal({
        modalType: 'CREATE_SYNTHESIS_PROJECT',
        modalData: { workspaceId, project, handleResetData: fetchProject },
      }),
    );

  const handleAdopt = async (prompt) => {
    const params = {
      ...(project.params || {}),
      meta_prompt: prompt,
      adopted_prompt: prompt,
    };
    const { status } = await updateSynthesisProject(projectId, { params });
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.promptAdopted'));
      fetchProject();
    }
  };

  const handleRun = async () => {
    const { status, message } = await runSynthesis(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.runStarted'));
      fetchProject();
    } else {
      toast.error(message);
    }
  };

  const running = project.status === 'running';

  const renderStep = () => {
    if (step === 0)
      return (
        <div className={cx('panel')}>
          <div className={cx('row')}>
            <b>{t('synthesis.info.module')}</b> {project.manifest_name} (
            {project.manifest_version})
          </div>
          <div className={cx('row')}>
            <b>{t('synthesis.info.metaPrompt')}</b>{' '}
            {project.params?.meta_prompt || '-'}
          </div>
          <div className={cx('row')}>
            <b>{t('synthesis.info.count')}</b> {project.params?.count ?? '-'} ·{' '}
            <b>GPU</b> {project.gpu_count}
          </div>
          <ButtonV2
            colorType='skyblue'
            label={t('synthesis.action.editConfig')}
            onClick={handleEdit}
            disabled={running}
          />
        </div>
      );
    if (step === 1)
      return (
        <div className={cx('panel')}>
          <p className={cx('hint')}>
            {t('synthesis.wizard.llm1Hint', { method: cand.method })}
            {cand.mock && <span className={cx('mock')}> [mock]</span>}
          </p>
          {cand.adopted_prompt && (
            <div className={cx('adopted')}>
              {t('synthesis.prompt.adopted', { prompt: cand.adopted_prompt })}
            </div>
          )}
          {cand.candidates.map((c, i) =>
            discarded.includes(i) ? null : (
              <div key={i} className={cx('cand')}>
                <span className={cx('score')}>{c.score}</span>
                <span className={cx('prompt')}>{c.prompt}</span>
                <ButtonV2
                  colorType='skyblue'
                  label={t('synthesis.action.adopt')}
                  onClick={() => handleAdopt(c.prompt)}
                />
                <ButtonV2
                  type='outline'
                  label={t('synthesis.action.discard')}
                  onClick={() => setDiscarded((d) => [...d, i])}
                />
              </div>
            ),
          )}
        </div>
      );
    if (step === 2)
      return (
        <div className={cx('panel')}>
          <div className={cx('row')}>
            <b>{t('status.label')}</b> {statusLabel(t, project.status)}
            {project.progress != null
              ? ` · ${Math.round(project.progress * 100)}%`
              : ''}
          </div>
          <ButtonV2
            colorType='blue'
            label={t('synthesis.wizard.runGenerate')}
            onClick={handleRun}
            disabled={running}
          />
          <div className={cx('result-count')}>
            {t('synthesis.card.resultCount', { n: result.total || 0 })}
          </div>
          {result.records.length > 0 && (
            <table className={cx('table')}>
              <thead>
                <tr>
                  <th>image</th>
                  <th>instruction</th>
                  <th>output</th>
                </tr>
              </thead>
              <tbody>
                {result.records.slice(0, 5).map((r, i) => (
                  <tr key={i}>
                    <td>{r.image || '-'}</td>
                    <td>{r.instruction || '-'}</td>
                    <td>{r.output || r.raw || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      );
    return (
      <div className={cx('panel')}>
        <div className={cx('placeholder')}>
          {t('synthesis.wizard.laterSteps')}
        </div>
      </div>
    );
  };

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
      <h1 className={cx('title')}>
        {t('synthesis.wizard.title', { name: project.name })}
      </h1>
      <p className={cx('jump')}>{t('synthesis.wizard.jump')}</p>

      <div className={cx('stepper')}>
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={cx('step', i === step && 'active', i < step && 'done')}
            onClick={() => setStep(i)}
          >
            <div className={cx('num')}>{i + 1}</div>
            <div className={cx('step-label')}>{t(s.labelKey)}</div>
            <div className={cx('step-sub')}>{t(s.subKey)}</div>
          </div>
        ))}
      </div>

      {renderStep()}

      <div className={cx('nav')}>
        <ButtonV2
          type='outline'
          label={t('synthesis.wizard.prev')}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        />
        <ButtonV2
          colorType='blue'
          label={t('synthesis.wizard.next')}
          onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
          disabled={step === STEPS.length - 1}
        />
      </div>
    </div>
  );
}
