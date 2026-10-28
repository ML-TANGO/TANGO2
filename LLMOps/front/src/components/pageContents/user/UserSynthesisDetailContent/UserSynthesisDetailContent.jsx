import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import {
  downloadSynthesisResult,
  getSynthesisLog,
  getSynthesisProject,
  getSynthesisResult,
  runSynthesis,
  saveSynthesisDataset,
} from '@src/apis/flightbase/synthesis';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisDetailContent.module.scss';

const cx = classNames.bind(style);

const MODULES = [
  {
    key: 'LLM1',
    labelKey: 'synthesis.module.llm1.label',
    descKey: 'synthesis.module.llm1.desc',
  },
  {
    key: 'LLM2',
    labelKey: 'synthesis.module.llm2.label',
    descKey: 'synthesis.module.llm2.desc',
  },
  {
    key: 'LLM3',
    labelKey: 'synthesis.module.llm3.label',
    descKey: 'synthesis.module.llm3.desc',
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

export default function UserSynthesisDetailContent() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [project, setProject] = useState(null);
  const [result, setResult] = useState({ records: [], total: 0 });
  const [log, setLog] = useState('');
  const [saveOpen, setSaveOpen] = useState(false);
  const [dsName, setDsName] = useState('');
  const loading = useRef(false);

  const fetchAll = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const { result: p, status } = await getSynthesisProject(projectId);
      if (status === STATUS_SUCCESS) setProject(p);
      const { result: r, status: rs } = await getSynthesisResult(projectId);
      if (rs === STATUS_SUCCESS && r) setResult(r);
      const { result: lg, status: ls } = await getSynthesisLog(projectId);
      if (ls === STATUS_SUCCESS && lg) setLog(lg.log || '');
    } finally {
      loading.current = false;
    }
  }, [projectId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (project?.status !== 'running') return undefined;
    const iv = setInterval(fetchAll, 3000);
    return () => clearInterval(iv);
  }, [project, fetchAll]);

  if (!project)
    return <div className={cx('cont')}>{t('synthesis.loading')}</div>;

  const handleRun = async () => {
    const { status, message } = await runSynthesis(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.runStarted'));
      fetchAll();
    } else {
      toast.error(message);
    }
  };

  const handleEdit = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_SYNTHESIS_PROJECT',
        modalData: { workspaceId, project, handleResetData: fetchAll },
      }),
    );
  };

  const handleDownload = async () => {
    try {
      const blob = await downloadSynthesisResult(projectId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `synthesis-${projectId}.jsonl`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(t('synthesis.toast.downloadFailed'));
    }
  };

  const handleSaveDataset = async () => {
    if (!dsName.trim()) {
      toast.error(t('synthesis.toast.datasetNameRequired'));
      return;
    }
    const { status, message } = await saveSynthesisDataset(projectId, {
      dataset_name: dsName.trim(),
    });
    if (status === STATUS_SUCCESS) {
      toast.success(t('synthesis.toast.datasetSaved'));
      setSaveOpen(false);
      setDsName('');
    } else {
      toast.error(message || t('synthesis.toast.datasetSaveFailed'));
    }
  };

  const running = project.status === 'running';
  const progressTxt =
    project.progress != null ? ` · ${Math.round(project.progress * 100)}%` : '';

  return (
    <div className={cx('cont')}>
      <div className={cx('top')}>
        <button
          className={cx('back-to-list')}
          onClick={() =>
            history.push(`/user/workspace/${workspaceId}/datasets/synthesis`)
          }
        >
          <img
            className={cx('back-btn-image')}
            src='/images/icon/00-ic-basic-arrow-02-left.svg'
            alt='<'
          />
          <span className={cx('back-btn-label')}>{t('synthesis.label')}</span>
        </button>
        <div className={cx('title-row')}>
          <span className={cx('field')}>{project.field || '-'}</span>
          <h1 className={cx('title')}>{project.name}</h1>
          <span className={cx('status', project.status)}>
            {statusLabel(t, project.status)}
            {running ? progressTxt : ''}
          </span>
        </div>
        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            label={t('synthesis.action.wizard')}
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/wizard`,
              )
            }
          />
          <ButtonV2
            type='outline'
            label={t('synthesis.action.canvas')}
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/canvas`,
              )
            }
          />
          <ButtonV2
            type='outline'
            label={t('synthesis.action.promptOptimize')}
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-optimize`,
              )
            }
          />
          <ButtonV2
            colorType='skyblue'
            label={t('synthesis.action.editConfig')}
            onClick={handleEdit}
            disabled={running}
          />
          <ButtonV2
            colorType='blue'
            label={t('synthesis.action.run')}
            onClick={handleRun}
            disabled={running}
          />
        </div>
      </div>

      <div className={cx('modules')}>
        {MODULES.map((m, i) => (
          <React.Fragment key={m.key}>
            <div className={cx('module', i === 1 && 'active')}>
              <div className={cx('mod-key')}>{m.key}</div>
              <div className={cx('mod-label')}>{t(m.labelKey)}</div>
              <div className={cx('mod-desc')}>{t(m.descKey)}</div>
              {i === 1 && (
                <div className={cx('mod-status')}>
                  {statusLabel(t, project.status)}
                  {running ? progressTxt : ''}
                </div>
              )}
            </div>
            {i < MODULES.length - 1 && <div className={cx('arrow')}>→</div>}
          </React.Fragment>
        ))}
      </div>

      <div className={cx('info')}>
        <div>
          <b>{t('synthesis.info.module')}</b>: {project.manifest_name} (
          {project.manifest_version})
        </div>
        <div>
          <b>{t('synthesis.info.metaPrompt')}</b>:{' '}
          {project.params?.meta_prompt || '-'}
        </div>
        <div>
          <b>{t('synthesis.info.optimizeMethod')}</b>:{' '}
          {project.params?.optimize_method || '-'}
        </div>
        <div>
          <b>{t('synthesis.info.count')}</b>: {project.params?.count ?? '-'}
        </div>
        <div>
          <b>GPU</b>: {project.gpu_count}
        </div>
      </div>

      {(log || running) && (
        <div className={cx('logwrap')}>
          <h2 className={cx('log-title')}>
            {t('synthesis.log.title')}{' '}
            {running && <span className={cx('live')}>● LIVE</span>}
          </h2>
          <pre className={cx('log-box')}>
            {log || t('synthesis.log.loading')}
          </pre>
        </div>
      )}

      <div className={cx('result')}>
        <div className={cx('result-head')}>
          <h2 className={cx('result-title')}>
            {t('synthesis.result.title')}{' '}
            {result.total
              ? t('synthesis.result.count', { n: result.total })
              : ''}
          </h2>
          {result.total > 0 && (
            <div className={cx('result-actions')}>
              <ButtonV2
                type='outline'
                label={t('synthesis.action.download')}
                onClick={handleDownload}
              />
              <ButtonV2
                colorType='skyblue'
                label={t('synthesis.action.saveDataset')}
                onClick={() => setSaveOpen((v) => !v)}
              />
            </div>
          )}
        </div>
        {saveOpen && (
          <div className={cx('save-row')}>
            <input
              className={cx('save-input')}
              placeholder={t('synthesis.dataset.namePlaceholder')}
              value={dsName}
              onChange={(e) => setDsName(e.target.value)}
            />
            <ButtonV2
              colorType='blue'
              label={t('saveBtn.label')}
              onClick={handleSaveDataset}
            />
            <ButtonV2
              type='outline'
              label={t('cancel.label')}
              onClick={() => setSaveOpen(false)}
            />
          </div>
        )}
        {result.records.length === 0 ? (
          <div className={cx('empty')}>{t('synthesis.result.empty')}</div>
        ) : (
          <table className={cx('table')}>
            <thead>
              <tr>
                <th>image</th>
                <th>instruction</th>
                <th>output</th>
              </tr>
            </thead>
            <tbody>
              {result.records.map((rec, i) => (
                <tr key={i}>
                  <td>{rec.image || '-'}</td>
                  <td>{rec.instruction || '-'}</td>
                  <td>{rec.output || rec.raw || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
