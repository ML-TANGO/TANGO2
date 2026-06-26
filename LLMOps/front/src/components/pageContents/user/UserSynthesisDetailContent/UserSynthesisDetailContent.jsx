import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  { key: 'LLM1', label: '프롬프트 생성기', desc: '메타프롬프트 → 최적 프롬프트/인스트럭션' },
  { key: 'LLM2', label: '데이터 생성기', desc: '데이터 생성 프롬프트 → 데이터 라벨' },
  { key: 'LLM3', label: '알고리즘 호출자', desc: 'API Call → 학습 알고리즘/환경' },
];

const statusLabel = (s) =>
  ({ created: '대기', running: '실행 중', completed: '완료', failed: '실패', cancelled: '취소' }[s] || s || '-');

export default function UserSynthesisDetailContent() {
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

  if (!project) return <div className={cx('cont')}>불러오는 중...</div>;

  const handleRun = async () => {
    const { status, message } = await runSynthesis(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success('생성 실행을 시작했습니다.');
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
      toast.error('다운로드에 실패했습니다.');
    }
  };

  const handleSaveDataset = async () => {
    if (!dsName.trim()) {
      toast.error('데이터셋 이름을 입력하세요.');
      return;
    }
    const { status, message } = await saveSynthesisDataset(projectId, {
      dataset_name: dsName.trim(),
    });
    if (status === STATUS_SUCCESS) {
      toast.success('데이터셋으로 저장했습니다.');
      setSaveOpen(false);
      setDsName('');
    } else {
      toast.error(message || '데이터셋 저장에 실패했습니다.');
    }
  };

  const running = project.status === 'running';
  const progressTxt =
    project.progress != null ? ` · ${Math.round(project.progress * 100)}%` : '';

  return (
    <div className={cx('cont')}>
      <div className={cx('top')}>
        <button
          className={cx('back')}
          onClick={() =>
            history.push(`/user/workspace/${workspaceId}/datasets/synthesis`)
          }
        >
          ← 목록
        </button>
        <div className={cx('title-row')}>
          <span className={cx('field')}>{project.field || '-'}</span>
          <h1 className={cx('title')}>{project.name}</h1>
          <span className={cx('status', project.status)}>
            {statusLabel(project.status)}
            {running ? progressTxt : ''}
          </span>
        </div>
        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            label='🧭 마법사'
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/wizard`,
              )
            }
          />
          <ButtonV2
            type='outline'
            label='🔗 캔버스'
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/canvas`,
              )
            }
          />
          <ButtonV2
            type='outline'
            label='⚙ 프롬프트 최적화'
            onClick={() =>
              history.push(
                `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-optimize`,
              )
            }
          />
          <ButtonV2
            colorType='skyblue'
            label='설정 수정'
            onClick={handleEdit}
            disabled={running}
          />
          <ButtonV2
            colorType='blue'
            label='생성 실행'
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
              <div className={cx('mod-label')}>{m.label}</div>
              <div className={cx('mod-desc')}>{m.desc}</div>
              {i === 1 && (
                <div className={cx('mod-status')}>
                  {statusLabel(project.status)}
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
          <b>생성 모듈</b>: {project.manifest_name} ({project.manifest_version})
        </div>
        <div>
          <b>메타프롬프트</b>: {project.params?.meta_prompt || '-'}
        </div>
        <div>
          <b>프롬프트 최적화</b>: {project.params?.optimize_method || '-'}
        </div>
        <div>
          <b>생성 개수</b>: {project.params?.count ?? '-'}
        </div>
        <div>
          <b>GPU</b>: {project.gpu_count}
        </div>
      </div>

      {(log || running) && (
        <div className={cx('logwrap')}>
          <h2 className={cx('log-title')}>
            실행 로그 {running && <span className={cx('live')}>● LIVE</span>}
          </h2>
          <pre className={cx('log-box')}>{log || '로그를 불러오는 중...'}</pre>
        </div>
      )}

      <div className={cx('result')}>
        <div className={cx('result-head')}>
          <h2 className={cx('result-title')}>
            생성 결과 {result.total ? `(${result.total}건)` : ''}
          </h2>
          {result.total > 0 && (
            <div className={cx('result-actions')}>
              <ButtonV2
                type='outline'
                label='결과 다운로드'
                onClick={handleDownload}
              />
              <ButtonV2
                colorType='skyblue'
                label='데이터셋으로 저장'
                onClick={() => setSaveOpen((v) => !v)}
              />
            </div>
          )}
        </div>
        {saveOpen && (
          <div className={cx('save-row')}>
            <input
              className={cx('save-input')}
              placeholder='새 데이터셋 이름'
              value={dsName}
              onChange={(e) => setDsName(e.target.value)}
            />
            <ButtonV2 colorType='blue' label='저장' onClick={handleSaveDataset} />
            <ButtonV2
              type='outline'
              label='취소'
              onClick={() => setSaveOpen(false)}
            />
          </div>
        )}
        {result.records.length === 0 ? (
          <div className={cx('empty')}>
            아직 생성된 데이터가 없습니다. “생성 실행” 후 확인하세요.
          </div>
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
