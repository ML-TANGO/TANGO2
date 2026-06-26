import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  { label: '데이터 준비', sub: '원천 데이터 + 사용자 입력' },
  { label: '프롬프트·인스트럭션 생성', sub: 'LLM1 · 최적화' },
  { label: '데이터 생성', sub: 'LLM2 · 데이터 라벨' },
  { label: '알고리즘 호출', sub: 'LLM3 · API Call' },
  { label: '학습 실행', sub: '학습 알고리즘/환경' },
  { label: '결과 모델', sub: 'SDx 특화 LLM · 평가' },
];

const statusLabel = (s) =>
  ({ created: '대기', running: '실행 중', completed: '완료', failed: '실패', cancelled: '취소' }[s] || s || '-');

export default function UserSynthesisWizardContent() {
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [step, setStep] = useState(0);
  const [project, setProject] = useState(null);
  const [cand, setCand] = useState({ candidates: [], method: 'OPRO', adopted_prompt: null, mock: false });
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

  if (!project) return <div className={cx('cont')}>불러오는 중...</div>;

  const handleEdit = () =>
    dispatch(
      openModal({
        modalType: 'CREATE_SYNTHESIS_PROJECT',
        modalData: { workspaceId, project, handleResetData: fetchProject },
      }),
    );

  const handleAdopt = async (prompt) => {
    const params = { ...(project.params || {}), meta_prompt: prompt, adopted_prompt: prompt };
    const { status } = await updateSynthesisProject(projectId, { params });
    if (status === STATUS_SUCCESS) {
      toast.success('프롬프트를 채택했습니다.');
      fetchProject();
    }
  };

  const handleRun = async () => {
    const { status, message } = await runSynthesis(projectId);
    if (status === STATUS_SUCCESS) {
      toast.success('생성 실행을 시작했습니다.');
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
          <div className={cx('row')}><b>생성 모듈</b> {project.manifest_name} ({project.manifest_version})</div>
          <div className={cx('row')}><b>메타프롬프트</b> {project.params?.meta_prompt || '-'}</div>
          <div className={cx('row')}><b>생성 개수</b> {project.params?.count ?? '-'} · <b>GPU</b> {project.gpu_count}</div>
          <ButtonV2 colorType='skyblue' label='설정 수정' onClick={handleEdit} disabled={running} />
        </div>
      );
    if (step === 1)
      return (
        <div className={cx('panel')}>
          <p className={cx('hint')}>
            LLM1 (프롬프트 생성기) · {cand.method}
            {cand.mock && <span className={cx('mock')}> [mock]</span>}
          </p>
          {cand.adopted_prompt && <div className={cx('adopted')}>✓ 채택됨: {cand.adopted_prompt}</div>}
          {cand.candidates.map((c, i) =>
            discarded.includes(i) ? null : (
              <div key={i} className={cx('cand')}>
                <span className={cx('score')}>{c.score}</span>
                <span className={cx('prompt')}>{c.prompt}</span>
                <ButtonV2 colorType='skyblue' label='✓ 채택' onClick={() => handleAdopt(c.prompt)} />
                <ButtonV2 type='outline' label='폐기' onClick={() => setDiscarded((d) => [...d, i])} />
              </div>
            ),
          )}
        </div>
      );
    if (step === 2)
      return (
        <div className={cx('panel')}>
          <div className={cx('row')}>
            <b>상태</b> {statusLabel(project.status)}
            {project.progress != null ? ` · ${Math.round(project.progress * 100)}%` : ''}
          </div>
          <ButtonV2 colorType='blue' label='데이터 생성 실행' onClick={handleRun} disabled={running} />
          <div className={cx('result-count')}>생성 데이터: {result.total || 0}건</div>
          {result.records.length > 0 && (
            <table className={cx('table')}>
              <thead><tr><th>image</th><th>instruction</th><th>output</th></tr></thead>
              <tbody>
                {result.records.slice(0, 5).map((r, i) => (
                  <tr key={i}><td>{r.image || '-'}</td><td>{r.instruction || '-'}</td><td>{r.output || r.raw || '-'}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      );
    return (
      <div className={cx('panel')}>
        <div className={cx('placeholder')}>
          후속 단계 — 고려대 LLM3(알고리즘 호출)·학습·결과 평가 연동 (P3).
        </div>
      </div>
    );
  };

  return (
    <div className={cx('cont')}>
      <button
        className={cx('back')}
        onClick={() => history.push(`/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/overview`)}
      >
        ← 개요
      </button>
      <h1 className={cx('title')}>{project.name} · 단계별 마법사</h1>
      <p className={cx('jump')}>↩ Jump 루프: 결과 보고 이전 단계로 회귀 재최적화</p>

      <div className={cx('stepper')}>
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={cx('step', i === step && 'active', i < step && 'done')}
            onClick={() => setStep(i)}
          >
            <div className={cx('num')}>{i + 1}</div>
            <div className={cx('step-label')}>{s.label}</div>
            <div className={cx('step-sub')}>{s.sub}</div>
          </div>
        ))}
      </div>

      {renderStep()}

      <div className={cx('nav')}>
        <ButtonV2 type='outline' label='← 이전 단계' onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0} />
        <ButtonV2 colorType='blue' label='다음 단계 →' onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))} disabled={step === STEPS.length - 1} />
      </div>
    </div>
  );
}
