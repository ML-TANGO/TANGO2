import { useCallback, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import { getPlayground, postDualProvision } from '@src/apis/llm/playground';
import { getInstancesList } from '@src/apis/llm/model';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DualDeployDetail.module.scss';

const cx = classNames.bind(style);
const GPU_OPTIONS = [1, 2, 4];

// 이중모델 배포 상세(배포측) — 단일 llmplayground 상세와 대칭.
//   생성 모달은 셸(이름+이중)만 만들고 여기로 이동. 여기서 LLM1/LLM2·인스턴스·모델별 GPU 를
//   선택해 provision(POST /playgrounds/dual-session/provision) → 배포 후 추론 탭 상세로 이동.
//   이미 프로비저닝된 세션으로 들어오면 추론 상세로 리다이렉트(구성=배포측 / 실행=추론).
const DualDeployDetail = () => {
  const match = useRouteMatch();
  const history = useHistory();
  const dispatch = useDispatch();
  const { id: workspaceId, pid } = match.params;

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  const [promptModel, setPromptModel] = useState(null);
  const [promptModelData, setPromptModelData] = useState(null);
  const [promptCommit, setPromptCommit] = useState(null);
  const [inferenceModel, setInferenceModel] = useState(null);
  const [inferenceModelData, setInferenceModelData] = useState(null);
  const [inferenceCommit, setInferenceCommit] = useState(null);
  const [instances, setInstances] = useState([]);
  const [instanceId, setInstanceId] = useState(null);
  const [promptGpuCount, setPromptGpuCount] = useState(1);
  const [inferenceGpuCount, setInferenceGpuCount] = useState(1);
  const [deploying, setDeploying] = useState(false);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Deployment' } }]));
  }, [dispatch]);

  const load = useCallback(async () => {
    const res = await getPlayground(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      const row = (res.result || []).find((r) => String(r.id) === String(pid));
      setSession(row || null);
      // 이미 프로비저닝(부모↔자식 링크됨)된 세션이면 추론 실행 화면으로.
      if (row && row.prompt_gen_playground_id) {
        history.replace(`/user/workspace/${workspaceId}/inference/${pid}`);
        return;
      }
    } else {
      errorToastMessage(res.error, res.message);
    }
    setLoading(false);
  }, [workspaceId, pid, history]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getInstancesList(workspaceId).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        setInstances(Array.isArray(res.result) ? res.result : []);
      }
    });
  }, [workspaceId]);

  const sameModel =
    promptModel != null && String(promptModel) === String(inferenceModel);
  const canDeploy =
    !!promptModel &&
    !!inferenceModel &&
    !sameModel &&
    !!instanceId &&
    !deploying;

  const handleDeploy = async () => {
    if (!canDeploy) return;
    setDeploying(true);
    try {
      const res = await postDualProvision({
        playground_id: pid,
        prompt_gen_model_id: promptModel,
        inference_model_id: inferenceModel,
        model_instance_id: instanceId,
        prompt_gen_commit_id: promptCommit,
        inference_commit_id: inferenceCommit,
        prompt_gen_gpu_count: promptGpuCount,
        inference_gpu_count: inferenceGpuCount,
      });
      if (res.status === STATUS_SUCCESS) {
        // 배포 시작 → 추론 상세(실행면)로. 상태 폴링은 추론쪽에서.
        history.push(`/user/workspace/${workspaceId}/inference/${pid}`);
        return;
      }
      errorToastMessage(res.error, res.message);
    } catch (e) {
      errorToastMessage(null, '이중모델 배포 중 오류가 발생했습니다.');
    } finally {
      setDeploying(false);
    }
  };

  if (loading) return <div className={cx('dual-cont')}>loading...</div>;

  return (
    <div className={cx('dual-cont')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>이중모델 배포 구성</h1>
        <span className={cx('sub')}>
          {session?.name ? `세션: ${session.name} · ` : ''}
          프롬프트 생성(LLM1)·추론(LLM2) 모델과 자원을 선택해 배포하세요.
        </span>
      </div>

      <div className={cx('form')}>
        <section className={cx('field')}>
          <h3 className={cx('field-title')}>프롬프트 생성 모델 (LLM1)</h3>
          <ModelSelector
            wid={workspaceId}
            selected={promptModel}
            onSelect={(id, d) => {
              setPromptModel(id);
              setPromptModelData(d);
              setPromptCommit(null);
            }}
            onCheckpointSelect={(id) => setPromptCommit(id)}
          />
        </section>

        <section className={cx('field')}>
          <h3 className={cx('field-title')}>추론 모델 (LLM2)</h3>
          <ModelSelector
            wid={workspaceId}
            selected={inferenceModel}
            onSelect={(id, d) => {
              setInferenceModel(id);
              setInferenceModelData(d);
              setInferenceCommit(null);
            }}
            onCheckpointSelect={(id) => setInferenceCommit(id)}
          />
        </section>
        {sameModel && (
          <p className={cx('warn')}>
            프롬프트 생성 모델과 추론 모델은 서로 달라야 합니다.
          </p>
        )}

        <section className={cx('field')}>
          <h3 className={cx('field-title')}>인스턴스 (두 모델에 각각 적용)</h3>
          {instances.length === 0 ? (
            <p className={cx('empty')}>사용 가능한 인스턴스가 없습니다.</p>
          ) : (
            <div className={cx('res-grid')}>
              {instances.map((ins) => (
                <button
                  key={ins.instance_id}
                  type='button'
                  className={cx(
                    'res-card',
                    String(instanceId) === String(ins.instance_id) &&
                      'selected',
                  )}
                  onClick={() => setInstanceId(ins.instance_id)}
                >
                  <span className={cx('res-name')}>{ins.instance_name}</span>
                  <span className={cx('res-meta')}>
                    GPU {ins.gpu_allocate ?? 0}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <div className={cx('gpu-cols')}>
          <section className={cx('field')}>
            <h3 className={cx('field-title')}>LLM1 GPU 수</h3>
            <div className={cx('chip-row')}>
              {GPU_OPTIONS.map((g) => (
                <button
                  key={g}
                  type='button'
                  className={cx('chip', promptGpuCount === g && 'selected')}
                  onClick={() => setPromptGpuCount(g)}
                >
                  {g}
                </button>
              ))}
            </div>
          </section>
          <section className={cx('field')}>
            <h3 className={cx('field-title')}>LLM2 GPU 수</h3>
            <div className={cx('chip-row')}>
              {GPU_OPTIONS.map((g) => (
                <button
                  key={g}
                  type='button'
                  className={cx('chip', inferenceGpuCount === g && 'selected')}
                  onClick={() => setInferenceGpuCount(g)}
                >
                  {g}
                </button>
              ))}
            </div>
          </section>
        </div>
        <p className={cx('note')}>
          * 두 모델을 각각 배포하므로 GPU {promptGpuCount + inferenceGpuCount}
          장을 점유합니다 (프롬프트 생성 {promptGpuCount} + 추론{' '}
          {inferenceGpuCount}).
          {promptModelData || inferenceModelData
            ? ` · LLM1: ${promptModelData?.name ?? '-'} / LLM2: ${inferenceModelData?.name ?? '-'}`
            : ''}
        </p>

        <div className={cx('actions')}>
          <button
            type='button'
            className={cx('cancel-btn')}
            onClick={() =>
              history.push(`/user/workspace/${workspaceId}/llmplayground`)
            }
          >
            취소
          </button>
          <button
            type='button'
            className={cx('deploy-btn', !canDeploy && 'disabled')}
            disabled={!canDeploy}
            onClick={handleDeploy}
          >
            {deploying ? '배포 중...' : '배포'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DualDeployDetail;
