import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Checkbox, InputText, Selectbox, Switch } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';

import {
  getRunningPlaygrounds,
  hasAnyRunningPlayground,
} from '@src/apis/llm/playground';
import { getGpuAvailability } from '@src/apis/flightbase/node';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';
import { moveRovingFocus } from '@src/utils/a11y';

import {
  BENCHMARK_CATEGORIES,
  BENCHMARK_MAP,
  FORMAT_TRAIN_BENCHMARK_IDS,
  GENERATION_METRICS,
  REFERENCE_BENCHMARKS,
  categoryCount,
  defaultMetricFor,
  recordedMetricsFor,
} from './benchmarks';
import { metricLabel } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// **정답 대조 평가** 실행 설정 — 단일 화면 모달. **평가할 모델·데이터셋도 여기서 고른다**
// (프로젝트는 이름·유형만 잠근다) — 한 프로젝트가 모델을 여러 개 견주는 것이 프로젝트의
// 목적이라 생성 시점에 잠글 수 없다. 그 위에 "무엇을(벤치마크 하나) / 무엇으로(실행 중인
// 배포)"를 고른다. 3단계 위저드였던 것을 한 화면으로 합친 이유:
//   · 한 런 = 벤치마크 하나이므로 목록 단계와 매핑 단계가 같은 한 줄을 두 번 묻고 있었다.
//   · 지표는 고를 것이 없다 — 채점기가 한 번에 내는 지표를 전부 기록한다. 그래서 선택
//     드롭다운을 없애고 "무엇이 기록되는지"만 레일에서 통보한다.
// onRun({ modelId, datasetId, benchmarks, inferencePlaygroundId }) 로 상위가 실행한다.
//
// **심판 설정은 여기 없다.** 정답 대조는 정답이 데이터에 있어 기계가 대조한다 — 심판 LLM 이
// 개입할 자리가 없고, 심판 배포·내장 심판·프롬프트 전략·심판 출력 상한은 전부 LLM 심사
// 실행 화면(JudgeRunConfig)의 것이다. 여기서 고를 수 있는 벤치마크도 REFERENCE_BENCHMARKS
// 로 좁혀, 화면에서만 고를 수 있고 서버에서 거부되는 조합이 생기지 않게 한다.
//
// **출력은 기본적으로 배포에서 가져온다** — 평가 컨테이너는 채점만 하고, 답변 생성은 이미 떠
// 있는 배포(inference_playground_id)에 요청한다. 컨테이너가 체크포인트를 직접 올려
// 생성하던 경로는 없앴다: 같은 질문에 답이 둘이면 어느 쪽이 채점됐는지가 화면에서 안 보이고,
// BE 도 이제 그 필드를 받지 않는다. 후보는 **고른 모델을 서빙 중인** 배포뿐이다.
//
// **예외 — 포맷 학습(MixATIS).** UGEN 처럼 고정 형식을 생성해야 채점되는 벤치마크는 형식을
// 배우지 않은 가중치로 재면 내용을 알아도 0 점이 나온다. 그 형식은 채점기가 로컬에 올린
// 모델에 LoRA 로 얹어 배우는 것이라 원격 배포에는 붙일 방법이 없다 → 포맷 학습을 켜면
// 생성 위임을 걷고, 고른 배포가 **서빙 중인 체크포인트**를 학습해 그대로 채점한다.
// 그래서 이 스위치가 켜지면 배포 절의 의미가 '출력을 만들 곳' → '학습할 체크포인트의
// 출처' 로 바뀌고, 체크포인트가 없는 배포(HF 모델 직접 배포)는 고를 수 없게 된다.
// BE 도 같은 배타·같은 경계를 강제한다(constants.FORMAT_TRAIN_MANIFEST_KEYS).

const BenchmarkRunConfig = ({
  workspaceId,
  modelOptions,
  datasetOptions,
  running,
  onRun,
  onClose,
}) => {
  const { t } = useTranslation();

  // 이 런이 평가할 대상 — 모델·데이터셋(단일). 프로젝트 상속이 아니라 런의 선택이다.
  //   목록은 상위(ProjectDetail)가 이미 조회한 것을 그대로 받는다(중복 조회 X).
  const [modelId, setModelId] = useState('');
  const [datasetId, setDatasetId] = useState('');

  const [picked, setPicked] = useState(''); // 벤치마크 id — 라디오(하나)
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [withGeneration, setWithGeneration] = useState(false);
  // 평가 전 형식 학습을 돌릴지. 지원 벤치마크를 고르면 **켠 상태로 시작**한다 — 형식을
  // 배우지 않은 가중치의 점수는 0 이라 그것이 기본값이어야 한다. 끄는 것은 "형식 미학습
  // 상태를 일부러 재 본다"는 진단 선택이다.
  const [formatTrain, setFormatTrain] = useState(false);
  // 플랫폼 GPU 풀 — null=아직 모름(미조회/로딩), false=조회 실패. 포맷 학습이 켜져
  // 있을 때만 묻는다(꺼져 있으면 이 런은 GPU 를 쓰지 않는다).
  const [gpu, setGpu] = useState(null);

  // 출력을 가져올 배포 — 평가 컨테이너가 모델을 새로 올리지 않고 이미 떠 있는 배포에 생성을
  // 요청한다. 고를 수 있는 건 **고른 모델을 서빙 중인 running 배포**뿐이다(다른 모델의 배포로
  // 생성하면 채점되는 것이 평가 대상이 아니게 된다). null=아직 모름(미조회/로딩).
  const [deployments, setDeployments] = useState(null);
  // 후보가 0 건일 때만 채우는 판정값 — 워크스페이스에 running 배포가 하나라도 있나.
  // null=아직 안 물어봄. 빈 상태 문구를 두 갈래로 가르는 데만 쓴다.
  const [anyRunning, setAnyRunning] = useState(null);
  const [playgroundId, setPlaygroundId] = useState('');

  // 고를 것이 하나뿐이면 기본 선택 — 어차피 그것밖에 못 고른다(배포 선택과 같은 규약).
  useEffect(() => {
    if (modelOptions?.length === 1)
      setModelId((prev) => prev || modelOptions[0].value);
  }, [modelOptions]);
  useEffect(() => {
    if (datasetOptions?.length === 1)
      setDatasetId((prev) => prev || datasetOptions[0].value);
  }, [datasetOptions]);

  // 모델을 바꾸면 배포 선택을 비운다 — 후보 목록이 모델로 걸러져 다시 조회되므로, 이전
  // 모델의 배포가 선택에 남아 있으면 목록에 없는 값이 그대로 실려 나간다.
  const pickModel = (nextId) => {
    setModelId(nextId);
    setPlaygroundId('');
    // 옛 모델의 후보가 한 프레임 남지 않게 즉시 '모름'으로 되돌린다(조회는 이펙트가 한다).
    setDeployments(null);
  };

  const selectedModel =
    (modelOptions || []).find((item) => item.value === modelId) || null;
  const selectedDataset =
    (datasetOptions || []).find((item) => item.value === datasetId) || null;

  const benchmark = picked ? BENCHMARK_MAP[picked] : null;
  const supportsFormatTrain =
    !!picked && FORMAT_TRAIN_BENCHMARK_IDS.includes(picked);
  const generationMetrics = picked ? GENERATION_METRICS[picked] : null;

  // 라디오 그룹(카드형) 참조 — 키보드 조작은 공용 moveRovingFocus 가 담당한다.
  const listGroupRef = useRef(null);

  const pickBenchmark = (id) => {
    const next = picked === id ? '' : id;
    setPicked(next);
    setWithGeneration(false);
    // 포맷 학습은 벤치마크에 매인 설정이다 — 벤치마크를 바꾸면 그 벤치마크의 기본값으로
    // 되돌린다. 남겨 두면 지원하지 않는 벤치마크에 켜진 채로 실행돼 BE 가 거절한다.
    setFormatTrain(FORMAT_TRAIN_BENCHMARK_IDS.includes(next));
  };

  // 출력을 가져올 배포 후보 — **고른 모델을 서빙 중인 running 배포**만 BE 가 내려 준다.
  // 모델이 정해지기 전에는 물어볼 것이 없으므로 조회하지 않는다(=모름). 모델을 바꾸면
  // 다시 조회한다 — 선택 비우기는 pickModel 이 맡는다.
  // 지난 런이 참조하던 배포는 나중에 내려갈 수 있어, 이력에는 남고 선택지에서만 빠진다.
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
      // 후보가 하나면 기본 선택 — 어차피 그것밖에 못 고른다.
      if (list.length === 1) setPlaygroundId(list[0].id);
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, modelId]);

  // 포맷 학습은 채점기가 체크포인트를 자기 GPU 에 올려 GPU 1장을 실제로 쓴다. 그런데
  // 스케줄러의 GPU claim 은 **대기열 없이 즉시 실패**하므로(GPU pin 없이 뜬 파드가 노드의
  // 모든 GPU 를 보는 것을 막는 의도적 방어), 못 띄우는 상태에서 실행하면 런이 만들어졌다가
  // failed 로 떨어져 이력만 남는다. 켤 때마다 현황을 다시 물어 최신값으로 판단한다.
  // 조회 실패는 false 로 두고 **실행을 막지 않는다** — 조회가 죽었다고 멀쩡한 클러스터에서
  // 실행까지 막으면 더 나쁘다(막는 것은 '가용 0' 을 실제로 확인했을 때뿐).
  useEffect(() => {
    if (!formatTrain) {
      setGpu(null);
      return undefined;
    }
    let cancelled = false;
    setGpu(null);
    (async () => {
      const res = await getGpuAvailability(workspaceId);
      if (cancelled) return;
      setGpu(res.status === STATUS_SUCCESS && res.result ? res.result : false);
    })();
    return () => {
      cancelled = true;
    };
  }, [formatTrain, workspaceId]);

  // NewStyleModalFrame 의 Esc 는 Redux 모달을 닫는다 — 로컬 조건부 렌더 경로라 직접 건다
  // (ExpertInferenceModal 과 같은 처리).
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // 검색은 **보이는 문구**를 훑는다 — 설명이 i18n 키가 된 뒤로 카탈로그의 원문을 훑으면
  // 화면에 뜬 문구와 다른 것을 검색하게 된다(영어 로케일에서 한국어로만 걸리는 식).
  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return REFERENCE_BENCHMARKS.filter(
      (b) =>
        (category === 'all' || b.category === category) &&
        (term === '' ||
          b.label.toLowerCase().includes(term) ||
          t(b.descKey).toLowerCase().includes(term)),
    );
  }, [category, query, t]);

  const recorded = useMemo(
    () => (picked ? recordedMetricsFor(picked, withGeneration) : []),
    [picked, withGeneration],
  );

  // 배포가 어느 커밋을 올렸는지는 목록이 이미 들고 온다(BE get_running_deployments 의
  // commit_id) — 되묻지 않는다. HF 모델을 직접 올린 배포는 플랫폼 커밋이 없어 null 이다.
  const hasCheckpoint = (d) => !!d?.commit_id;

  const deploymentOptions = useMemo(
    () =>
      (deployments ?? []).map((d) => {
        // 포맷 학습은 **이 배포가 올린 체크포인트를 학습**한다 — 커밋이 없는 배포로는
        // 성립하지 않는다. 고르게 두고 실행 시점에 422 를 주는 대신 고를 수 없게 하고,
        // 왜 못 고르는지를 이름 옆에 붙인다(비활성만 하면 이유가 화면에 없다).
        const blocked = formatTrain && !hasCheckpoint(d);
        return {
          label: blocked
            ? `${d.name} — ${t('evaluation.bench.deployNoCheckpoint')}`
            : d.name,
          value: d.id,
          isDisable: blocked,
        };
      }),
    [deployments, formatTrain, t],
  );
  const selectedDeployment =
    deploymentOptions.find((item) => item.value === playgroundId) || null;
  const deployment = (deployments ?? []).find((d) => d.id === playgroundId);

  // 후보 중 체크포인트를 내놓는 배포 수 — 0 이면 드롭다운은 떠 있는데 전부 비활성이라,
  // 이유를 절 안에 세우지 않으면 사용자가 막힌 곳을 알 수 없다.
  const checkpointDeployCount = (deployments ?? []).filter(hasCheckpoint).length;

  // 포맷 학습을 켜는 순간 이미 고른 배포가 자격을 잃을 수 있다 — 비운다. 그대로 두면
  // 목록에서 비활성인 값이 선택으로 남아 실행까지 실려 나간다(모델 변경 시 비우는 것과
  // 같은 취지). 선택이 비면 아래 blockReason 이 사유를 세운다.
  useEffect(() => {
    if (!formatTrain || !playgroundId) return;
    const current = (deployments ?? []).find((d) => d.id === playgroundId);
    if (current && !hasCheckpoint(current)) setPlaygroundId('');
  }, [formatTrain, playgroundId, deployments]);

  const categoryOptions = BENCHMARK_CATEGORIES.map((item) => ({
    label: `${t(item.labelKey)} (${categoryCount(item.id)})`,
    value: item.id,
  }));
  const selectedCategory =
    categoryOptions.find((item) => item.value === category) ||
    categoryOptions[0];

  // 각 축이 채워졌나 — 레일의 warn 강조와 푸터 문구가 같은 판정을 쓴다.
  // 출력은 배포에서만 가져오므로 배포 선택이 곧 이 축의 충족 조건이다(BE 도 필수로 받는다).
  const sourceReady = !!playgroundId;

  // 실행을 막는 첫 이유 하나. 푸터에 그대로 세워, 왜 버튼이 죽어 있는지가 항상 보이게 한다.
  // (BE 도 같은 경계를 강제하지만 거기까지 가면 어느 칸이 문제인지 모르는 422 만 남는다.)
  // 화면에 세우는 숫자는 **워크스페이스 몫**이다 — 사용자가 '내 몫' 으로 이해하는 축이고
  // 플랫폼의 다른 화면도 그렇게 말한다. 클러스터 전체를 세면 남의 워크스페이스 GPU 까지
  // 내 것처럼 보인다.
  const gpuWs = gpu && gpu.workspace ? gpu.workspace : null;

  // 차단은 **둘 중 빡빡한 쪽**을 따른다. 워크스페이스 쿼터는 실행을 막지 못하고(external
  // 경로가 읽지 않고 차트도 nvidia.com/gpu 를 요청하지 않아 K8s 쿼터가 증가조차 않는다)
  // 실제 게이트는 클러스터 풀이다. 반대로 클러스터에 여유가 있어도 워크스페이스 몫이 0
  // 이면 사용자에게는 없는 것과 같다. 가용 0 을 **확인했을 때만** 막는다 — null(로딩)/
  // false(조회 실패)는 '모름' 이라 막지 않는다(확신 없이 막으면 멀쩡한 클러스터가 봉쇄된다).
  const gpuWsBlocked = !!(formatTrain && gpuWs && gpuWs.free === 0);
  const gpuClusterBlocked = !!(formatTrain && gpu && gpu.free === 0);
  const gpuBlocked = gpuWsBlocked || gpuClusterBlocked;

  const blockReason = !modelId
    ? t('evaluation.run.needModel')
    : !datasetId
      ? t('evaluation.run.needDataset')
      : !picked
        ? t('evaluation.bench.needBenchmark')
        : !sourceReady
          ? // 포맷 학습이 켜져 있으면 배포는 출력이 아니라 **학습할 체크포인트**의 출처다
            // — 같은 빈 칸이라도 채워야 할 것이 다르므로 문구를 가른다.
            t(
              formatTrain
                ? 'evaluation.bench.needCheckpointDeploy'
                : 'evaluation.bench.needDeployment',
            )
          : gpuBlocked
            ? // 왜 막혔는지가 다르다 — 내 몫이 없는 것과 클러스터가 다 찬 것은 사용자가
              // 할 일이 다르다(전자는 쿼터 증설, 후자는 다른 작업이 끝나기를 기다림).
              t(
                gpuWsBlocked
                  ? 'evaluation.bench.gpuNone'
                  : 'evaluation.bench.gpuNoneCluster',
              )
            : null;

  const summary =
    blockReason ||
    t(
      formatTrain
        ? 'evaluation.bench.runSummaryFormat'
        : 'evaluation.bench.runSummary',
      {
        benchmark: benchmark?.label,
        deployment: deployment?.name || '-',
        count: recorded.length,
      },
    );

  const handleRun = () => {
    if (blockReason || running) return null;
    // 메트릭은 서버가 권장값으로 고정한다(dto.BenchmarkSelection — 받기만 하고 버린다).
    // 그래도 실어 보내는 이유는 화면과 서버가 서로 다른 시점에 배포돼도 런이 깨지지 않게
    // 하기 위해서다 — 옛 서버는 metric 을 요구하고, 새 서버는 무시한다.
    return onRun({
      // 이 런이 평가할 대상 — 상위가 model_id / dataset_ids 로 싣는다.
      modelId,
      datasetId,
      benchmarks: [{ benchmark: picked, metric: defaultMetricFor(picked) }],
      // 배포 — 필수다. 포맷 학습이 꺼져 있으면 컨테이너가 이 배포의 답변을 채점만 하고,
      // 켜져 있으면 이 배포가 서빙 중인 체크포인트를 학습해 컨테이너가 직접 생성·채점한다
      // (둘은 배타 — BE 가 같은 배타를 강제한다).
      inferencePlaygroundId: playgroundId,
      formatTrain,
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
        type='benchmarkRunConfig'
        title={modalTitle}
        footerMessage={summary}
        submit={{
          text: running ? 'evaluation.running' : 'evaluation.runBenchmark',
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
            <section className={cx('panel')}>
              <div className={cx('panel-head')}>
                <div>
                  <h3 className={cx('panel-title')}>
                    {t('evaluation.bench.referenceTitle')}
                  </h3>
                  <p className={cx('panel-desc')}>
                    {t('evaluation.bench.referenceDesc')}
                  </p>
                </div>
                <div className={cx('filters')}>
                  <Selectbox
                    list={categoryOptions}
                    selectedItem={selectedCategory}
                    onChange={(item) => setCategory(item.value)}
                    customStyle={{
                      selectboxForm: { width: '170px' },
                      listForm: { width: '170px' },
                    }}
                  />
                  <InputText
                    size='medium'
                    value={query}
                    placeholder={t('evaluation.bench.searchPlaceholder')}
                    leftIcon='/images/icon/ic-search.svg'
                    closeIcon='/images/icon/close-c.svg'
                    disableLeftIcon={false}
                    disableClearBtn={false}
                    onChange={(e) => setQuery(e.target.value)}
                    onClear={() => setQuery('')}
                    customStyle={{ width: '190px' }}
                  />
                </div>
              </div>

              <div
                ref={listGroupRef}
                className={cx('benchmark-grid')}
                role='radiogroup'
                aria-label={t('evaluation.bench.selectBenchTitle')}
                onKeyDown={moveRovingFocus(
                  listGroupRef,
                  visible.map((b) => b.id),
                  picked,
                  pickBenchmark,
                )}
              >
                {visible.map((b) => {
                  const on = picked === b.id;
                  return (
                    <button
                      key={b.id}
                      type='button'
                      role='radio'
                      aria-checked={on}
                      data-value={b.id}
                      tabIndex={
                        on || (!picked && b.id === visible[0]?.id) ? 0 : -1
                      }
                      className={cx('benchmark-option', on && 'selected')}
                      onClick={() => pickBenchmark(b.id)}
                    >
                      <span className={cx('pick-radio')} aria-hidden='true' />
                      <span className={cx('option-body')}>
                        <span className={cx('bo-name')}>
                          {b.label}
                          {b.requiresFormat && (
                            <Badge
                              label={t('evaluation.bench.badgeFormat')}
                              type='yellow'
                              size='sm'
                            />
                          )}
                        </span>
                        <span className={cx('bo-desc')}>{t(b.descKey)}</span>
                      </span>
                    </button>
                  );
                })}
                {visible.length === 0 && (
                  <div className={cx('grid-empty')}>
                    <EmptyBox
                      text='evaluation.noSearchResult'
                      isBox
                      customStyle={{ height: '120px' }}
                    />
                  </div>
                )}
              </div>
            </section>
          </div>

          <aside className={cx('rail')}>
            <div className={cx('panel', 'rail-panel')}>
              {/* ⓪ 평가할 모델·데이터셋 — 런이 소유한다. 프로젝트에 잠겨 있던 것을 여기로
                  옮긴 이유: 한 프로젝트에서 모델·데이터셋을 바꿔 가며 재는 것이 비교의
                  전제인데, 생성 시점에 잠그면 프로젝트가 '모델 폴더'가 되어 버린다. */}
              <div className={cx('rail-sec')}>
                <p className={cx('rail-title')}>
                  {t('evaluation.run.subjectTitle')}
                </p>
                <div className={cx('opt-field')}>
                  <span className={cx('opt-label')}>
                    {t('evaluation.selectModel')}
                  </span>
                  {(modelOptions || []).length === 0 ? (
                    <p className={cx('rail-note', 'err')}>
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
                <div className={cx('opt-field')}>
                  <span className={cx('opt-label')}>
                    {t('evaluation.selectDatasets')}
                  </span>
                  {(datasetOptions || []).length === 0 ? (
                    <p className={cx('rail-note', 'err')}>
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

              {/* ① 포맷 학습 — 평가 전에 출력 규약을 학습할지. 아래 배포 절보다 **먼저**
                  두는 이유는 이 스위치가 배포 절의 의미를 바꾸기 때문이다: 켜면 배포가
                  '출력을 만들 곳'이 아니라 '학습할 체크포인트의 출처'가 되고, 체크포인트가
                  없는 배포는 후보에서 빠진다. 지원하는 벤치마크에서만 보인다. */}
              {supportsFormatTrain && (
                <div className={cx('rail-sec')}>
                  <p className={cx('rail-title')}>
                    {t('evaluation.bench.formatTrainTitle')}
                    <Switch
                      name='format-train'
                      checked={formatTrain}
                      onChange={() => setFormatTrain((v) => !v)}
                    />
                  </p>
                  <p className={cx('rail-note')}>
                    {t(
                      formatTrain
                        ? 'evaluation.bench.formatTrainOnNote'
                        : 'evaluation.bench.formatTrainOffNote',
                    )}
                  </p>
                  {/* GPU 현황 — 켰을 때만. 가용 0 이면 실행을 막으므로 왜 막혔는지가
                      같은 자리에 보여야 한다. 조회 중/실패는 숫자를 지어내지 않는다. */}
                  {formatTrain && gpu !== null && (
                    <p className={cx('rail-note', gpuBlocked && 'err')}>
                      {gpu === false
                        ? t('evaluation.bench.gpuUnknown')
                        : t('evaluation.bench.gpuStat', {
                            // 워크스페이스 몫이 있으면 그것으로, 없으면(쿼터 미설정 등)
                            // 클러스터 값으로 폴백한다 — 숫자를 비우지는 않는다.
                            total: gpuWs ? gpuWs.hard : gpu.total,
                            used: gpuWs ? gpuWs.used : gpu.in_use + gpu.reserved,
                            free: gpuWs ? gpuWs.free : gpu.free,
                          })}
                    </p>
                  )}
                </div>
              )}

              {/* ② 출력을 어디서 가져오나 — 이미 떠 있는 배포에 생성을 요청한다(GPU 를 새로
                  잡지 않는다). 후보는 위에서 고른 모델을 서빙 중인 배포뿐이라, 모델을 고르기
                  전에는 물어볼 것이 없다. 이 절은 '무엇을 평가하나'(⓪)가 아니라 '그 답변을
                  누가 만드나'를 정한다 — 포맷 학습이 켜지면 '어느 체크포인트를 학습하나'가
                  된다(제목이 함께 바뀐다). */}
              <div className={cx('rail-sec')}>
                <p className={cx('rail-title')}>
                  {t(
                    formatTrain
                      ? 'evaluation.bench.checkpointSourceTitle'
                      : 'evaluation.run.sourceTitle',
                  )}
                </p>
                {!modelId ? (
                  <p className={cx('rail-note')}>
                    {t('evaluation.run.sourceNeedModel')}
                  </p>
                ) : deployments === null ? (
                  <p className={cx('rail-note')}>
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
                      <ul className={cx('rail-meta')}>
                        {deployment.description && (
                          <li>{deployment.description}</li>
                        )}
                        <li>{deployment.deploy_type || 'cluster'}</li>
                      </ul>
                    )}
                  </>
                )}
                <p className={cx('rail-note')}>
                  {t('evaluation.bench.targetDeployNote')}
                </p>
                {/* 후보는 있는데 **전부 체크포인트가 없는** 경우 — 드롭다운이 통째로
                    비활성이라 이유를 여기서 말하지 않으면 막힌 곳을 알 수 없다. 나머지
                    형식 관련 설명은 포맷 학습 절의 한 줄이 대신한다. */}
                {formatTrain &&
                  deploymentOptions.length > 0 &&
                  checkpointDeployCount === 0 && (
                    <p className={cx('rail-note', 'err')}>
                      {t('evaluation.bench.noCheckpointDeploy')}
                    </p>
                  )}
              </div>

              {/* ③ 기록될 지표 — 통보만 한다. 한 번의 채점에서 나오는 지표는 전부 남는다. */}
              {benchmark && (
                <div className={cx('rail-sec')}>
                  <p className={cx('rail-title')}>
                    {t('evaluation.bench.recordedMetrics')}
                    <Badge
                      label={String(recorded.length)}
                      type='blue'
                      size='sm'
                    />
                  </p>
                  <ul className={cx('metric-plan')}>
                    {recorded.map((m) => (
                      <li
                        key={m}
                        className={cx(m === benchmark.recommended && 'rec')}
                      >
                        {metricLabel(t, m) || m}
                        {m === benchmark.recommended && (
                          <Badge
                            label={t('evaluation.bench.representative')}
                            type='blue'
                            size='sm'
                          />
                        )}
                      </li>
                    ))}
                  </ul>
                  {generationMetrics && (
                    <div className={cx('gen-opt')}>
                      <Checkbox
                        checked={withGeneration}
                        onChange={() => setWithGeneration((v) => !v)}
                        label={t('evaluation.bench.addGenMetrics', {
                          metrics: generationMetrics
                            .map((m) => metricLabel(t, m) || m)
                            .join(' · '),
                        })}
                      />
                      <Badge
                        label={t('evaluation.bench.genCost')}
                        type='yellow'
                        size='sm'
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>
      </NewStyleModalFrame>
    </div>
  );
};

export default BenchmarkRunConfig;
