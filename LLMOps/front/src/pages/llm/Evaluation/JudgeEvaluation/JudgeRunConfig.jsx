import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Selectbox } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';

import {
  getRunningPlaygrounds,
  hasAnyRunningPlayground,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';
import { moveRovingFocus } from '@src/utils/a11y';

import {
  JUDGE_BENCHMARKS,
  defaultMetricFor,
} from '../BenchmarkEvaluation/benchmarks';

import classNames from 'classnames/bind';
import benchStyle from '../BenchmarkEvaluation/BenchmarkEvaluation.module.scss';
import style from './JudgeEvaluation.module.scss';

// 모달 껍데기(run-config·run-main·rail)와 폼 규격(run-form·run-sec·run-label·run-note…)은
// **정답 대조의 스타일시트를 그대로 쓴다** — 폼 규격은 그 시트가 @import 하는
// Evaluation/_runModal.scss 에서 오고, 세 실행 모달(정답 대조·심사·전문가)이 같은 한 벌이다.
// 같은 레이아웃 언어를 두 벌 복제해 두면 한쪽만 고쳐져 서서히 갈라진다. 여기 스타일시트에서
// 오는 것은 심사 전용 카드(set-*)뿐이고, 이름이 겹치면 정답 대조 쪽이 이기도록 뒤에 편다.
const cx = classNames.bind({ ...style, ...benchStyle });

// **LLM 심사** 실행 설정 — 정답 대조(BenchmarkRunConfig)와 같은 단일 화면 모달이다.
// 좌: 심사 세트 하나(라디오) / 우: 레일(평가 대상 → 출력 배포 → 심판 배포 → 세부 설정) /
// 하단: 실행을 막는 첫 이유 + 취소·실행. 종전에는 별도 라우트(/runs/new)의 전체 페이지라
// 목록에서 벗어났다 돌아와야 했고, 같은 것을 고르는 두 유형이 서로 다른 화면 문법을 썼다.
//
// 종전의 "자유 샘플 + 기준 4종(정확성·관련성·유창성·안전성)" 경로는 폐기했다 — 기준 점수는
// mock 이었고(해시), 외부 API 심판(ChatGPT/Claude/Gemini·로컬 URL + 키)은 평가가 아니라
// 배포 표면의 문제라 그리로 옮긴다. 남은 것은 실제로 채점되는 것 하나뿐이다.
//
// 실행 경로는 **정답 대조와 같은 엔드포인트**다 — LogicKor 는 벤치마크이므로
// runBenchmark({ benchmarks: ['logickor'], ... }) 로 나간다. 심사 전용 엔드포인트는 없다.
// BE 는 프로젝트 유형(judge)과 벤치마크 유형이 어긋나면 런 생성을 거부한다.
//
// 심판은 **떠 있는 배포로 일원화**한다(judge_playground_id) — 컨테이너가 심판 가중치를
// GPU 에 또 올리는 내장 심판(judge_model) 경로는 BE 에 남아 있지만 화면에서는 감춘다.
// 평가 대상으로 고른 배포는 심판 후보에서 빠진다: 자기 답을 자기가 채점하면
// (self-preference) 점수를 믿을 수 없고, BE 도 같은 조합을 거부한다.
// 심판 후보는 **모델로 거르지 않는다** — 대상과 다른 모델이 채점해야 하므로 대상 모델로
// 좁히면 후보가 곧 자기 자신뿐이 되어 항상 0 개가 된다.

// 심사 세트 카드. JUDGE_BENCHMARKS 가 실제로 돌릴 수 있는 것 전부이고, 그 뒤에 붙는
// 자리는 "아직 못 돈다"를 보이게 두는 비활성 항목이다 — 목록에서 지워 버리면 사용자는
// 우리가 그것을 모르는 줄 알고 계속 묻게 된다. 정본(benchmarks.js)에는 넣지 않는다:
// 그 목록의 id 는 BE constants.BENCHMARK_IDS 와 1:1 이라 채점기 없는 id 를 넣으면
// 화면에서 고를 수 있고 서버가 422 로 거절하는 조합이 생긴다.
const UNAVAILABLE_SETS = [
  { id: 'mtbench', label: 'MT-Bench', descKey: 'evaluation.judge.setMtbench' },
];

const JudgeRunConfig = ({
  workspaceId,
  modelOptions,
  datasetOptions,
  running,
  onRun,
  onClose,
}) => {
  const { t } = useTranslation();

  // 이 런이 채점할 대상(단일). BE 계약: model_id / dataset_ids(1개).
  const [modelId, setModelId] = useState('');
  const [datasetId, setDatasetId] = useState('');

  // 심사 세트 — 지금은 고를 것이 하나뿐이라 기본 선택한다(배포 선택과 같은 규약).
  const [setId, setSetId] = useState(JUDGE_BENCHMARKS[0]?.id || '');
  // 카드형 라디오라 방향키 조작을 직접 건다(공용 moveRovingFocus). 비활성 세트
  // (UNAVAILABLE_SETS)는 값 목록에서 뺀다 — 넘어가면 고를 수 없는 자리에 갇힌다.
  const setGroupRef = useRef(null);
  const setValues = JUDGE_BENCHMARKS.map((b) => b.id);

  // 출력을 가져올 배포 — 채점 컨테이너는 생성하지 않고 이미 떠 있는 배포에 요청한다.
  // 후보는 **고른 모델을 서빙 중인** running 배포뿐이다. null=아직 모름(미조회/로딩).
  const [deployments, setDeployments] = useState(null);
  // 후보가 0 건일 때만 채우는 판정값 — 워크스페이스에 running 배포가 하나라도 있나.
  const [anyRunning, setAnyRunning] = useState(null);
  const [playgroundId, setPlaygroundId] = useState('');

  // 심판 배포 — 필수다. 심사는 심판이 없으면 채점 자체가 성립하지 않는다.
  const [judgePool, setJudgePool] = useState(null); // null=아직 모름
  const [judgePlaygroundId, setJudgePlaygroundId] = useState('');

  // 세부 설정 — 전부 선택이다. 비우면 채점 컨테이너 기본값이 그대로 쓰인다.

  // 고를 것이 하나뿐이면 기본 선택 — 어차피 그것밖에 못 고른다.
  useEffect(() => {
    if (modelOptions?.length === 1)
      setModelId((prev) => prev || modelOptions[0].value);
  }, [modelOptions]);
  useEffect(() => {
    if (datasetOptions?.length === 1)
      setDatasetId((prev) => prev || datasetOptions[0].value);
  }, [datasetOptions]);

  // 모델을 바꾸면 배포 선택을 비운다 — 후보가 모델로 걸러져 다시 조회되므로, 이전 모델의
  // 배포가 선택에 남으면 목록에 없는 값이 그대로 실려 나간다.
  const pickModel = (nextId) => {
    setModelId(nextId);
    setPlaygroundId('');
    setDeployments(null);
  };

  // 평가 대상 배포 후보 — 모델이 정해져야 물어볼 것이 생긴다.
  useEffect(() => {
    if (!workspaceId || !modelId) {
      setDeployments(null);
      return undefined;
    }
    let cancelled = false;
    setDeployments(null);
    setAnyRunning(null);
    (async () => {
      const res = await getRunningPlaygrounds(workspaceId, modelId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        setDeployments([]);
        return;
      }
      const list = Array.isArray(res.result) ? res.result : [];
      // 후보가 없을 때만 워크스페이스 전체를 한 번 더 물어본다 — 문구가 한 프레임 뒤에
      // 바뀌지 않도록 판정이 끝난 뒤에 빈 상태를 렌더한다.
      if (list.length === 0) {
        const any = await hasAnyRunningPlayground(workspaceId);
        if (cancelled) return;
        setAnyRunning(any);
      }
      setDeployments(list);
      if (list.length === 1) setPlaygroundId(list[0].id);
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, modelId]);

  // 심판 후보는 워크스페이스의 실행 중 배포 전체다(모델 필터 없음 — 위 머리말 참조).
  useEffect(() => {
    if (!workspaceId) return undefined;
    let cancelled = false;
    (async () => {
      const res = await getRunningPlaygrounds(workspaceId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        setJudgePool([]);
        return;
      }
      setJudgePool(Array.isArray(res.result) ? res.result : []);
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  // 평가 대상으로 고른 배포가 심판으로도 잡혀 있으면 심판 선택을 비운다.
  useEffect(() => {
    if (playgroundId && judgePlaygroundId === playgroundId) {
      setJudgePlaygroundId('');
    }
  }, [playgroundId, judgePlaygroundId]);

  // NewStyleModalFrame 의 Esc 는 Redux 모달을 닫는다 — 로컬 조건부 렌더 경로라 직접 건다
  // (BenchmarkRunConfig 와 같은 처리).
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const selectedModel =
    (modelOptions || []).find((item) => item.value === modelId) || null;
  const selectedDataset =
    (datasetOptions || []).find((item) => item.value === datasetId) || null;

  const deploymentOptions = useMemo(
    () => (deployments ?? []).map((d) => ({ label: d.name, value: d.id })),
    [deployments],
  );
  const selectedDeployment =
    deploymentOptions.find((item) => item.value === playgroundId) || null;
  const deployment = (deployments ?? []).find((d) => d.id === playgroundId);

  const judgeOptions = useMemo(
    () =>
      (judgePool ?? [])
        .filter((d) => d.id !== playgroundId)
        .map((d) => ({ label: d.name, value: d.id })),
    [judgePool, playgroundId],
  );
  const selectedJudge =
    judgeOptions.find((item) => item.value === judgePlaygroundId) || null;

  // 실행을 막는 첫 이유 하나. 푸터에 그대로 세워, 왜 버튼이 죽어 있는지가 항상 보이게 한다.
  // (BE 도 같은 경계를 강제하지만 거기까지 가면 어느 칸이 문제인지 모르는 422 만 남는다.)
  const blockReason = !setId
    ? t('evaluation.judge.needSet')
    : !modelId
      ? t('evaluation.run.needModel')
      : !datasetId
        ? t('evaluation.run.needDataset')
        : !playgroundId
          ? t('evaluation.bench.needDeployment')
          : !judgePlaygroundId
            ? t('evaluation.bench.needJudge')
            : null;

  const summary =
    blockReason ||
    t('evaluation.judge.runSummary', {
      set: JUDGE_BENCHMARKS.find((b) => b.id === setId)?.label || setId,
      deployment: deployment?.name || '-',
      judge: selectedJudge?.label || '-',
    });

  const handleRun = () => {
    if (blockReason || running) return null;
    // 정답 대조 런과 같은 계약으로 올린다 — 상위가 runBenchmark 로 보낸다.
    // metric 은 서버가 권장값으로 고정하지만(받기만 하고 버린다) 옛 서버 호환을 위해 싣는다.
    return onRun({
      modelId,
      datasetId,
      benchmarks: [{ benchmark: setId, metric: defaultMetricFor(setId) }],
      inferencePlaygroundId: playgroundId,
      judgePlaygroundId,
    });
  };

  const modalTitle = t('evaluation.project.detail.newRun');

  return (
    <div
      onClick={(event) => {
        // NewStyleModalFrame 은 오버레이에 id={title} 을 건다 — 바깥을 누르면 닫는다.
        if (event.target.id === modalTitle) onClose();
      }}
    >
      <NewStyleModalFrame
        type='judgeRunConfig'
        title={modalTitle}
        footerMessage={summary}
        submit={{
          text: running ? 'evaluation.running' : 'evaluation.judge.run',
          func: handleRun,
        }}
        cancel={{ text: 'cancel.label', func: onClose }}
        validate={!blockReason && !running}
        isResize
        isMinimize
        // 기본 폭 664px 은 2단(목록 + 320px 레일)을 담지 못한다.
        customStyle={{ width: '1080px', maxWidth: 'calc(100vw - 48px)' }}
      >
        <div className={cx('run-config')}>
          <div className={cx('run-main')}>
            {/* 심사 세트 — 무엇으로 채점하나. 먼저 서는 이유: 세트가 곧 문항·영역·척도다. */}
            <div className={cx('run-heading')}>
              <h3 className={cx('run-sec-title')}>
                {t('evaluation.judge.setTitle')}
              </h3>
              <p className={cx('run-prose')}>{t('evaluation.judge.setDesc')}</p>
            </div>

            <div
              ref={setGroupRef}
              className={cx('set-list')}
              role='radiogroup'
              aria-label={t('evaluation.judge.setTitle')}
              onKeyDown={moveRovingFocus(
                setGroupRef,
                setValues,
                setId,
                setSetId,
              )}
            >
              {JUDGE_BENCHMARKS.map((b) => (
                <button
                  key={b.id}
                  type='button'
                  role='radio'
                  aria-checked={setId === b.id}
                  data-value={b.id}
                  tabIndex={
                    setId === b.id || (!setId && b.id === setValues[0])
                      ? 0
                      : -1
                  }
                  className={cx('set-item', setId === b.id && 'on')}
                  onClick={() => setSetId(b.id)}
                >
                  <span className={cx('set-radio')} aria-hidden='true' />
                  <span className={cx('set-body')}>
                    <span className={cx('set-name')}>{b.label}</span>
                    <span className={cx('set-desc')}>{t(b.descKey)}</span>
                  </span>
                </button>
              ))}
              {UNAVAILABLE_SETS.map((item) => (
                <button
                  key={item.id}
                  type='button'
                  role='radio'
                  aria-checked={false}
                  aria-disabled='true'
                  disabled
                  className={cx('set-item', 'off')}
                  onClick={() => {}}
                >
                  <span className={cx('set-radio')} aria-hidden='true' />
                  <span className={cx('set-body')}>
                    <span className={cx('set-name')}>
                      {item.label}
                      <Badge
                        label={t('evaluation.judge.setUnavailable')}
                        type='gray'
                        size='sm'
                      />
                    </span>
                    <span className={cx('set-desc')}>{t(item.descKey)}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <aside className={cx('rail')}>
            <div className={cx('run-form')}>
              {/* ⓪ 채점할 모델·데이터셋 — 런이 소유한다(프로젝트는 이름·유형만 잠근다). */}
              <div className={cx('run-sec')}>
                <p className={cx('run-sec-title')}>
                  {t('evaluation.run.subjectTitle')}
                </p>
                <div className={cx('run-field')}>
                  <span className={cx('run-label')}>
                    {t('evaluation.selectModel')}
                    <span className={cx('req')}>*</span>
                  </span>
                  {(modelOptions || []).length === 0 ? (
                    <p className={cx('run-hint', 'err')}>
                      {t('evaluation.compare.noModels')}
                    </p>
                  ) : (
                    <Selectbox
                      list={modelOptions}
                      selectedItem={selectedModel}
                      placeholder={t('select.label')}
                      onChange={(item) => pickModel(item.value)}
                      customStyle={{
                        selectboxForm: { width: '100%' },
                        listForm: { width: '100%' },
                      }}
                    />
                  )}
                </div>
                <div className={cx('run-field')}>
                  <span className={cx('run-label')}>
                    {t('evaluation.selectDatasets')}
                    <span className={cx('req')}>*</span>
                  </span>
                  {(datasetOptions || []).length === 0 ? (
                    <p className={cx('run-hint', 'err')}>
                      {t('evaluation.noDatasets')}
                    </p>
                  ) : (
                    <Selectbox
                      type='search'
                      list={datasetOptions}
                      selectedItem={selectedDataset}
                      placeholder={t('evaluation.searchDataset')}
                      onChange={(item) => setDatasetId(item.value)}
                      scrollAutoFocus={true}
                      customStyle={{
                        selectboxForm: { width: '100%' },
                        listForm: { width: '100%' },
                      }}
                    />
                  )}
                </div>
              </div>

              {/* ① 출력을 어디서 가져오나 — 채점 컨테이너는 생성하지 않고 이미 떠 있는
                  배포에 요청한다. 후보는 위에서 고른 모델을 서빙 중인 배포뿐이다.
                  빈 상태가 두 갈래(이 모델용만 없음 / 워크스페이스에 아무 배포도 없음)라
                  선택 상자를 비활성으로 세우는 대신 판정이 끝난 뒤 문구를 갈라 렌더한다. */}
              <div className={cx('run-sec')}>
                <p className={cx('run-sec-title')}>
                  {t('evaluation.run.sourceTitle')}
                  <span className={cx('req')}>*</span>
                </p>
                <div className={cx('run-field')}>
                  {!modelId ? (
                    <p className={cx('run-hint')}>
                      {t('evaluation.run.sourceNeedModel')}
                    </p>
                  ) : deployments === null ? (
                    <p className={cx('run-hint')}>
                      {t('evaluation.project.loading')}
                    </p>
                  ) : deploymentOptions.length === 0 ? (
                    <EmptyBox
                      text={
                        anyRunning
                          ? 'evaluation.run.sourceNoneForModel'
                          : 'evaluation.run.sourceNone'
                      }
                      isBox
                      customStyle={{
                        minHeight: '96px',
                        padding: '12px 14px',
                        boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                    <>
                      <Selectbox
                        list={deploymentOptions}
                        selectedItem={selectedDeployment}
                        placeholder={t('select.label')}
                        onChange={(item) => setPlaygroundId(item.value)}
                        customStyle={{
                          selectboxForm: { width: '100%' },
                          listForm: { width: '100%' },
                        }}
                      />
                      {deployment && (
                        <ul className={cx('run-meta')}>
                          {deployment.description && (
                            <li>{deployment.description}</li>
                          )}
                          <li>{deployment.deploy_type || 'cluster'}</li>
                        </ul>
                      )}
                    </>
                  )}
                </div>
                <p className={cx('run-note')}>
                  {t('evaluation.bench.targetDeployNote')}
                </p>
              </div>

              {/* ② 누가 채점하나 — 필수. 대상으로 고른 배포는 후보에서 빠지고(자기 채점),
                  후보를 대상 모델로 좁히지 않는다(좁히면 자기 자신뿐이 된다). */}
              <div className={cx('run-sec')}>
                <p className={cx('run-sec-title')}>
                  {t('evaluation.judge.judgeDeployTitle')}
                  <span className={cx('req')}>*</span>
                </p>
                <div className={cx('run-field')}>
                  {judgePool === null ? (
                    <p className={cx('run-hint')}>
                      {t('evaluation.project.loading')}
                    </p>
                  ) : judgeOptions.length === 0 ? (
                    <EmptyBox
                      text='evaluation.bench.noJudgeDeploy'
                      isBox
                      customStyle={{
                        minHeight: '96px',
                        padding: '12px 14px',
                        boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                    <Selectbox
                      list={judgeOptions}
                      selectedItem={selectedJudge}
                      placeholder={t('select.label')}
                      onChange={(item) => setJudgePlaygroundId(item.value)}
                      customStyle={{
                        selectboxForm: { width: '100%' },
                        listForm: { width: '100%' },
                      }}
                    />
                  )}
                </div>
                <p className={cx('run-micro')}>
                  {t('evaluation.bench.judgeNote')}
                </p>
              </div>
            </div>
          </aside>
        </div>
      </NewStyleModalFrame>
    </div>
  );
};

export default JudgeRunConfig;
