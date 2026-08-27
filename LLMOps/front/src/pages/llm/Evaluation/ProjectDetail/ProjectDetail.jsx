import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import {
  NavLink,
  Redirect,
  Route,
  Switch,
  useHistory,
  useLocation,
  useRouteMatch,
} from 'react-router-dom';

import { Badge, ButtonV2, Loading } from '@jonathan/ui-react';

import BenchmarkRunConfig from '../BenchmarkEvaluation/BenchmarkRunConfig';
import {
  BENCHMARK_LABEL,
  BENCHMARK_MAP,
  defaultMetricFor,
} from '../BenchmarkEvaluation/benchmarks';
import {
  formatMetricValue,
  metricLabel,
  normalizedScore,
} from '../BenchmarkEvaluation/benchmarkMetrics';
import EvalComparison from '../EvalComparison/EvalComparison';
import ExpertInferenceModal from '../ExpertEvaluation/ExpertInferenceModal';
import ExpertRunView from '../ExpertEvaluation/ExpertRunView';
import JudgeResultView from '../JudgeEvaluation/JudgeResultView';
import JudgeRunConfig from '../JudgeEvaluation/JudgeRunConfig';

import EvalGenerateModal from './EvalGenerateModal';

import ContentBox from '@src/components/molecules/ContentBox';
import EmptyBox from '@src/components/molecules/EmptyBox';
import MultiSortTable from '@src/components/molecules/MultiSortTable';

import {
  compareProjectRuns,
  deleteEvalRun,
  getEvalDatasets,
  getEvalProject,
  listEvalProjects,
  markEvalStatus,
  runBenchmark,
  runEvalInference,
  startExpert,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { addNineHours, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ProjectDetail.module.scss';

const cx = classNames.bind(style);

// 유형은 **채점 주체**로 가른다 — 기계가 정답과 대조(reference) / 다른 LLM 이 판단(judge) /
// 사람이 검수(expert). 종전 'benchmark' 는 앞의 둘이 섞여 있어 한 유형 안에서 점수의
// 척도가 달랐다(0~1 정답률 vs 1~10 심판 점수).
const TYPE_KEYS = {
  reference: 'evaluation.project.type.reference',
  judge: 'evaluation.project.type.judge',
  expert: 'evaluation.project.type.expert',
};

// 실행 목록을 펼친 표로 그리는 유형 — 런이 (무엇을 잰 런인가, 점수) 축을 갖는 유형이다.
// expert 는 그 축이 없어(사람이 샘플을 훑는 세션) 카드 목록을 유지한다.
const RUN_TABLE_TYPES = ['reference', 'judge'];
const STATUS_KEYS = {
  created: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
};
const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};
const TYPE_BADGE_TYPE = {
  reference: 'blue',
  judge: 'yellow',
  expert: 'green',
};

const fmtDate = (v) => addNineHours(v) || '-';

// run 메트릭 프리뷰 포맷 — expert 스케일(/5·%) 구분, 그 외 기본. (EvalComparison 과 동형.)
const fmtRunMetric = (k, v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  if (k === 'expert_avg_score') return `${v.toFixed(2)}/5`;
  if (k === 'expert_pass_rate') return `${v.toFixed(2)}%`;
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

// SimpleNav 는 llmModel.info.name 을 titleName 보다 우선하므로 평가 프로젝트명이 모델명에
// 오염될 수 있다. 마크업·클래스 구조는 그대로 따르되 평가 데이터만 받는 전용 헤더로 분리한다.
const EvaluationNav = ({ navList, topButtonList, titleName, subTitle }) => {
  const { t } = useTranslation();

  return (
    <div className={cx('nav-box')}>
      <div className={cx('title')}>
        <div className={cx('name')}>
          <div>{titleName}</div>
          {subTitle && <div className={cx('sub-title')}>{subTitle}</div>}
        </div>
        {topButtonList && <div className={cx('btn')}>{topButtonList}</div>}
      </div>
      <ul className={cx('nav')}>
        {navList.map(({ label, path: navPath }) => (
          <li className={cx('nav-item')} key={navPath}>
            <NavLink exact to={navPath} activeClassName={cx('active')}>
              <span className={cx('link-name')}>{t(label)}</span>
              <span className={cx('stick')} />
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
};

// 네비게이션이라 button 을 유지한다 — div+onClick 은 Tab 으로 도달할 수 없어
// 키보드 사용자가 목록으로 돌아갈 방법이 사라진다. 아이콘 이름은 옆 라벨이 주므로 alt=''.
const DetailBack = ({ label, onClick }) => (
  <button type='button' className={cx('back-to-list')} onClick={onClick}>
    <img
      className={cx('back-btn-image')}
      src='/images/icon/00-ic-basic-arrow-02-left.svg'
      alt=''
    />
    <span className={cx('back-btn-label')}>{label}</span>
  </button>
);

// 평가 프로젝트 상세(P3+P4). 실행 목록·설정·결과·전문가 채점·비교를 URL로 승격해
// 딥링크와 새로고침을 보장한다. 모델/데이터셋은 프로젝트에서 상속하며 하위 뷰 계약은 유지한다.
const ProjectDetail = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const location = useLocation();
  const match = useRouteMatch();
  const { id: workspaceId, projectId } = match.params;
  const { path, url } = match;
  const runsPath = `${url}/runs`;
  const comparePath = `${url}/compare`;
  const normalizedPath = location.pathname.replace(/\/+$/, '');

  const [project, setProject] = useState(null); // null=로딩
  const [runsData, setRunsData] = useState(null); // { metric_keys, best, runs }
  const [notFound, setNotFound] = useState(false);
  const [modelMap, setModelMap] = useState({}); // model_id에서 name으로 매핑
  const [datasetMap, setDatasetMap] = useState({}); // dataset_id에서 name으로 매핑
  // 런 실행 모달이 고르는 선택지 — 이름 매핑과 **같은 응답**에서 만든다(조회를 새로 만들지 않는다).
  const [modelOptions, setModelOptions] = useState([]);
  const [datasetOptions, setDatasetOptions] = useState([]);
  const [projectListUpdate, setProjectListUpdate] = useState(null);
  const [starting, setStarting] = useState(false);
  const [showInferModal, setShowInferModal] = useState(false);
  const [showGenModal, setShowGenModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [compareData, setCompareData] = useState(null);
  // 벤치마크 실행 설정은 인라인 위저드에서 단일 화면 모달로 옮겼다 — 한 런이 고르는 것은
  // 벤치마크 하나·배포 하나뿐이라 별도 화면(라우트)을 차지할 이유가 없다.
  const [showRunConfig, setShowRunConfig] = useState(false);
  // 새 실행 직후 아직 목록 응답에 없는 run의 결과 뷰 props를 URL 전환 사이에 보존한다.
  const [activeRun, setActiveRun] = useState(null);

  const fetchProject = useCallback(async () => {
    const res = await getEvalProject(projectId);
    if (res.status === STATUS_SUCCESS && res.result?.project) {
      setProject(res.result.project);
      setRunsData(res.result.runs || { metric_keys: [], best: {}, runs: [] });
    } else {
      setNotFound(true);
      errorToastMessage(res.error, res.message);
    }
  }, [projectId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    fetchProject();
  }, [dispatch, fetchProject]);

  // 모델명·데이터셋명 매핑(상세 메타 표시용) — 1회 조회. 실패해도 #id 로 폴백.
  useEffect(() => {
    if (!workspaceId) return undefined;
    let cancelled = false;
    (async () => {
      const [modelRes, datasetRes, projectListRes] = await Promise.all([
        callApi({
          url: `models?workspace_id=${workspaceId}`,
          method: 'GET',
        }),
        getEvalDatasets(workspaceId),
        listEvalProjects(workspaceId),
      ]);
      if (cancelled) return;
      if (modelRes.status === STATUS_SUCCESS) {
        const list = Array.isArray(modelRes.result)
          ? modelRes.result
          : (modelRes.result?.list ?? []);
        const map = {};
        list.forEach((m) => {
          if (m?.id != null) map[m.id] = m.name;
        });
        setModelMap(map);
        setModelOptions(
          list
            .filter((m) => m?.id != null)
            .map((m) => ({ label: m.name || `#${m.id}`, value: m.id })),
        );
      }
      if (datasetRes.status === STATUS_SUCCESS) {
        const list = Array.isArray(datasetRes.result)
          ? datasetRes.result
          : (datasetRes.result?.list ?? []);
        const map = {};
        list.forEach((dataset) => {
          const id = dataset.id ?? dataset.dataset_id;
          if (id != null) map[id] = dataset.name ?? dataset.dataset_name;
        });
        setDatasetMap(map);
        setDatasetOptions(
          list
            .map((dataset) => {
              const id = dataset.id ?? dataset.dataset_id;
              const dsName = dataset.name ?? dataset.dataset_name;
              const format = dataset.format ?? dataset.data_format ?? null;
              return {
                label: format ? `${dsName} (${format})` : dsName,
                value: id,
              };
            })
            .filter((option) => option.value != null),
        );
      }
      if (projectListRes.status === STATUS_SUCCESS) {
        const list = projectListRes.result?.projects ?? [];
        const current = list.find(
          (item) => String(item.id) === String(projectId),
        );
        setProjectListUpdate(current?.update_datetime ?? null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, workspaceId]);

  // 러너 generate 런이 running 인 동안 프로젝트를 폴링한다. 완료되어 runsData가 갱신되면 genRunning이
  // false 가 되어 폴링이 멈추고, 배너가 '생성 완료'로 전환 + 채점이 그 output 을 소비 가능.
  useEffect(() => {
    const running = (runsData?.runs ?? []).some(
      (r) => r.metric_set === 'inference' && r.status === 'running',
    );
    if (!running) return undefined;
    const timer = setInterval(() => {
      fetchProject();
    }, 4000);
    return () => clearInterval(timer);
  }, [runsData, fetchProject]);

  // 러너 inference 런(metric_set='inference')은 점수 런이 아니라 "생성" 서브스텝 — 점수 목록에서
  // 분리(클릭 시 dead-end 방지)하고, 최신 완료본은 배너/benchmark seam(inference_job_id)에 쓴다.
  //
  // ⚠️ 두 목록은 **반드시 memo 여야 한다** — 아래 runDatasetMap·benchRows 의 의존성이라,
  //    본문에서 매 렌더 새 배열을 만들면 그 memo 들이 무관한 상태 변경(모달 열림·실행 중
  //    플래그 등)에도 전부 다시 돌아 benchRows→bestRunByPair→benchColumns 사슬이 통째로
  //    재계산된다(= memo 를 붙여 둔 뜻이 사라진다).
  const allRuns = useMemo(() => runsData?.runs ?? [], [runsData]);
  const runs = useMemo(
    () => allRuns.filter((r) => r.metric_set !== 'inference'),
    [allRuns],
  );
  // 아래 둘은 allRuns 가 안정되면 함께 안정된다 — find 는 같은 원소 참조를, some 은 원시값을
  // 돌려주므로 별도 memo 없이도 참조가 흔들리지 않는다.
  const latestInference = allRuns.find(
    (r) => r.metric_set === 'inference' && r.status === 'completed',
  );
  const genRunning = allRuns.some(
    (r) => r.metric_set === 'inference' && r.status === 'running',
  );
  const metricKeys = runsData?.metric_keys ?? [];

  // 프로젝트 응답에는 데이터셋 ID만 있으므로 목록 API 이름을 우선하고, 실행 응답 이름으로 보강한다.
  const runDatasetMap = useMemo(() => {
    const map = {};
    runs.forEach((run) => {
      if (run.dataset_id != null && run.dataset_name) {
        map[run.dataset_id] = run.dataset_name;
      }
    });
    return map;
  }, [runs]);

  // ── 벤치마크 실행 목록(펼친 표) ────────────────────────────────────────────
  // 한 행 = 런 하나가 잰 **(벤치마크, 지표) 쌍 하나**다. 런 하나가 여러 행이 될 수 있다.
  //
  // 종전엔 런당 한 행만 만들고 metric_set CSV 의 **첫 쌍만** 읽었다. 정답 대조는 한 런에
  // 벤치마크를 여러 개(BE 상한 20) 담을 수 있으므로, mmlu+arc 를 한 번에 돌리면 둘 다
  // 채점됐는데(metrics = {mmlu, arc}) 화면에는 MMLU 한 줄만 남았다 — 사용자는 잰 줄 아는데
  // 값이 어디에도 안 보이는 **조용한 소실**이라, 못 잰 것보다 나쁘다.
  //
  // 그래서 CSV 의 모든 쌍으로 행을 펼친다(flatMap). 정렬·그룹 경계·Best 는 전부 쌍 단위로
  // 성립하므로(같은 벤치마크·지표끼리만 견준다) 펼친 행이 오히려 그 축의 제 단위다.
  // LLM 심사 런은 metric_set 이 "logickor:judge_overall" 하나뿐이라 행 수가 그대로다.
  const benchRows = useMemo(() => {
    if (!RUN_TABLE_TYPES.includes(project?.eval_type)) return [];
    return runs.flatMap((run) => {
      // metric_set = "benchmark:metric" CSV(신). 구 런은 metric-id CSV(콜론 없음)라
      // 벤치마크를 알 수 없고 지표만 남는다 — 그때는 지표 열만 채운다.
      // 빈 문자열 토큰 하나로 폴백해 **metric_set 이 비어도 런이 목록에서 사라지지 않게** 한다.
      const tokens = String(run.metric_set || '')
        .split(',')
        .map((token) => token.trim())
        .filter(Boolean);
      return (tokens.length ? tokens : ['']).map((token, order) => {
        const [head, tail] = token.split(':');
        let benchmark = null;
        let metric = null;
        if (tail) {
          benchmark = head;
          metric = tail;
        } else if (BENCHMARK_MAP[head]) {
          benchmark = head;
          metric = defaultMetricFor(head);
        } else if (head) {
          metric = head;
        }
        // 점수는 metrics(averages) 에서 읽는다 — 신 스키마는 벤치마크 id 가(쌍마다 제
        // 점수가 나온다), 구 스키마는 지표 id 가 키다.
        const scoreKey = benchmark || metric;
        const raw = scoreKey ? run.metrics?.[scoreKey] : null;
        const score =
          typeof raw === 'number' && !Number.isNaN(raw) ? raw : null;
        return {
          run,
          // CSV 안의 자리. 같은 런의 행끼리 순서를 고정하는 tiebreaker 이자, 중복 쌍이
          // 섞인 옛 런에서도 행 키가 겹치지 않게 하는 마지막 구분자다.
          order,
          benchmark,
          metric,
          score,
          pair: `${benchmark}::${metric}`,
          // ⚠️ run.id 만으로는 키가 겹친다 — 한 런이 여러 행이 되는 순간 React 가 행을
          //    잘못 재사용해 다른 벤치마크의 셀이 남는다.
          key: `${run.id}:${benchmark ?? ''}:${metric ?? ''}:${order}`,
        };
      });
    });
  }, [project?.eval_type, runs]);

  // 같은 (벤치마크, 지표) 를 **서로 다른 런에서** 2회 이상 잰 경우에만 Best 를 표시한다 —
  // 비교 대상이 없는 값에 붙는 Best 는 정보가 아니다.
  const bestRunByPair = useMemo(() => {
    const groups = {};
    benchRows.forEach((row) => {
      if (!row.benchmark || row.run.status !== 'completed' || row.score == null)
        return;
      const list = (groups[row.pair] = groups[row.pair] || []);
      // 한 런이 같은 쌍으로 두 번 들어오면(중복 CSV 토큰) 자기 자신을 비교 대상으로 세어
      // 단독 값에 Best 가 붙는다. 그룹은 **런 단위로** 유일해야 한다.
      if (list.some((item) => item.run.id === row.run.id)) return;
      list.push(row);
    });
    const best = {};
    Object.entries(groups).forEach(([pair, list]) => {
      if (list.length < 2) return;
      best[pair] = list.reduce((a, b) => (b.score > a.score ? b : a)).run.id;
    });
    return best;
  }, [benchRows]);

  // 체크포인트 열은 **있을 때만** 세운다. 출력 획득이 배포로 일원화된 뒤 새 런의
  // run.checkpoint 는 항상 비어 있어(모델 열이 이미 '모델 via 배포' 로 출처를 말한다)
  // 열 전체가 '-' 로만 채워진다. 그렇다고 지워 버리면 그 필드가 남아 있는 옛 런의
  // 유일한 구분 축이 사라지므로, 한 행이라도 값이 있을 때만 렌더한다.
  const hasCheckpoint = useMemo(
    () => benchRows.some((row) => !!row.run.checkpoint),
    [benchRows],
  );

  const benchLabelOf = (row) =>
    row.benchmark ? BENCHMARK_LABEL[row.benchmark] || row.benchmark : '';
  const metricLabelOf = (row) =>
    row.metric ? metricLabel(t, row.metric) || row.metric : '';
  // 심사 런에서 이 런을 가르는 축은 지표가 아니라 **누가 채점했나**다 — 같은 세트를 같은
  // 모델에 돌려도 심판이 다르면 다른 점수가 나온다. 배포명은 런 요약의 additive 필드로
  // 온다(생성 배포의 source_deployment 와 짝). 옛 런에는 없으므로 '-' 가 정상이다.
  const judgeLabelOf = (row) =>
    row.run.judge_deployment || row.run.judge_model || '';
  const cmpText = (a, b) => String(a).localeCompare(String(b), 'ko');

  // 런 1건 중지 — 지금까지는 진행 중 런을 멈추는 유일한 방법이 '삭제'였다. LogicKor 실채점은
  //   GPU 1장을 최대 1시간 잡으므로, 기록은 남기고 자원만 회수하는 경로가 따로 필요하다.
  //   markEvalStatus('cancelled') 는 DB 마킹 + 컨테이너 cancel 전달까지 BE 가 처리한다.
  const handleStopRun = useCallback(
    (run, e) => {
      e.stopPropagation();
      // ⚠️ 이 경로의 model_id 는 라우팅이 아니라 **authZ 바인딩**이다 — BE 가
      //   `WHERE ... AND source_model_id = %s` 로 다른 모델의 job 마킹을 막는다.
      //   프로젝트가 다중 모델이 된 지금 project.model_id 를 쓰면 런의 실제 모델과 어긋나
      //   예외가 아니라 **0행 갱신으로 조용히 실패**한다(눌러도 아무 일도 안 일어난다).
      const runModelId = run?.model_id ?? project.model_id;
      if (!run?.job_id || runModelId == null) return;
      dispatch(
        openConfirm({
          title: 'evaluation.run.stop.title',
          content: 'evaluation.run.stop.message',
          testid: 'eval-run-stop-modal',
          submit: {
            text: 'evaluation.run.stop.confirm',
            func: async () => {
              const res = await markEvalStatus(
                runModelId,
                run.job_id,
                'cancelled',
              );
              if (res.status !== STATUS_SUCCESS) {
                errorToastMessage(res.error, res.message);
                return;
              }
              await fetchProject();
            },
          },
          cancel: { text: 'cancel.label' },
        }),
      );
    },
    [dispatch, project, fetchProject],
  );

  // 런 1건 삭제(진행중/완료 모두). 프로젝트 삭제와 동일하게 네이티브 확인 모달(openConfirm) 재사용.
  //   행 클릭(openRun) 과 겹치지 않게 stopPropagation. 삭제 후 목록 갱신.
  const handleDeleteRun = useCallback(
    (run, e) => {
      e.stopPropagation();
      // 중지와 같은 이유로 런의 모델에 바인딩한다(위 handleStopRun 주석 참조).
      const runModelId = run?.model_id ?? project.model_id;
      if (!run?.job_id || runModelId == null) return;
      dispatch(
        openConfirm({
          title: 'evaluation.run.delete.title',
          content: 'evaluation.run.delete.message',
          testid: 'eval-run-delete-modal',
          submit: {
            text: 'delete.label',
            func: async () => {
              // 진행 중인 컨테이너 백엔드 런(benchmark/judge)은 삭제 전에 취소해 자원 회수
              //   (expert=컨테이너 없음). 취소는 best-effort — 실패해도 삭제는 진행.
              if (run.status === 'running' && project.eval_type !== 'expert') {
                await markEvalStatus(runModelId, run.job_id, 'cancelled');
              }
              const res = await deleteEvalRun(runModelId, run.job_id);
              if (res.status !== STATUS_SUCCESS) {
                errorToastMessage(res.error, res.message);
                return;
              }
              await fetchProject();
            },
          },
          cancel: { text: 'cancel.label' },
        }),
      );
    },
    [dispatch, project, fetchProject],
  );

  // 실행 목록의 앞 두 열은 **유형마다 뜻이 다르다**. 나머지(점수·모델·출처·실행 일자·
  // 상태·동작)는 유형과 무관하게 같은 것을 담으므로 공유한다.
  //   정답 대조 — 무엇을 잰 런인가(벤치마크) / 어느 축으로 읽나(지표). 점수는 0~1 · %.
  //   LLM 심사 — 어느 세트인가 / 누가 채점했나(심판 배포). 점수는 1~10.
  // 열 이름만 바꾸고 내용은 같게 두면 "MMLU 의 지표"와 "LogicKor 의 심판"이 한 열에
  // 섞여, 정렬·그룹 경계가 서로 다른 것을 같은 축으로 묶는다.
  const isJudgeProject = project?.eval_type === 'judge';
  const leadColumns = useMemo(() => {
    if (isJudgeProject) {
      return [
        {
          key: 'benchmark',
          label: t('evaluation.judge.colSet'),
          categorical: true,
          groupValue: (row) => row.benchmark,
          compare: (a, b) => cmpText(benchLabelOf(a), benchLabelOf(b)),
          render: (row) =>
            row.benchmark ? (
              <span className={cx('cell-bench')}>{benchLabelOf(row)}</span>
            ) : (
              <span className={cx('cell-dim')}>-</span>
            ),
        },
        {
          key: 'judge',
          label: t('evaluation.judge.colJudgeDeploy'),
          categorical: true,
          groupValue: (row) => judgeLabelOf(row),
          compare: (a, b) => cmpText(judgeLabelOf(a), judgeLabelOf(b)),
          render: (row) => {
            const label = judgeLabelOf(row);
            return label ? (
              <span className={cx('cell-metric')} title={label}>
                {label}
              </span>
            ) : (
              <span className={cx('cell-dim')}>-</span>
            );
          },
        },
      ];
    }
    return [
      {
        key: 'benchmark',
        label: t('evaluation.bench.colBenchShort'),
        categorical: true,
        groupValue: (row) => row.benchmark,
        compare: (a, b) => cmpText(benchLabelOf(a), benchLabelOf(b)),
        render: (row) =>
          row.benchmark ? (
            <span className={cx('cell-bench')}>{benchLabelOf(row)}</span>
          ) : (
            <span className={cx('cell-dim')}>-</span>
          ),
      },
      {
        key: 'metric',
        label: t('evaluation.metric'),
        categorical: true,
        groupValue: (row) => row.metric,
        compare: (a, b) => cmpText(metricLabelOf(a), metricLabelOf(b)),
        render: (row) =>
          row.metric ? (
            <span className={cx('cell-metric')}>{metricLabelOf(row)}</span>
          ) : (
            <span className={cx('cell-dim')}>-</span>
          ),
      },
    ];
    // benchLabelOf / metricLabelOf / judgeLabelOf 는 렌더마다 새로 만들어지는 포매터라
    // 의존성에 넣으면 memo 가 매번 깨진다. 이들이 닫는 바깥 값은 t 뿐이고 그 t 는 이미
    // 아래 의존성에 있으므로, 함수 자체를 빼도 로케일 변경이 누락되지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, isJudgeProject]);

  const benchColumns = useMemo(
    () => [
      ...leadColumns,
      {
        key: 'score',
        label: t('evaluation.bench.score'),
        defaultDir: 'desc',
        // 표시는 지표별 척도 그대로, 비교만 만점 대비로 정규화한다 — 안 그러면 0~1 지표가
        // 늘 꼴찌로 가라앉아 '점수' 정렬이 사실상 '척도' 정렬이 된다.
        compare: (a, b) =>
          (normalizedScore(a.metric, a.score) ?? -Infinity) -
          (normalizedScore(b.metric, b.score) ?? -Infinity),
        render: (row) => {
          if (row.score == null)
            return <span className={cx('cell-dim')}>-</span>;
          const isBest = bestRunByPair[row.pair] === row.run.id;
          return (
            <span className={cx('cell-score', isBest && 'best')}>
              {formatMetricValue(row.metric, row.score)}
              {isBest && <Badge label='Best' type='green' size='sm' />}
            </span>
          );
        },
      },
      // 답을 만든 모델. 체크포인트 런은 프로젝트 모델이 그대로 오고, 배포에 위임한 런은
      // 그 배포가 서빙하는 모델이 온다(프로젝트 모델과 다를 수 있어 배포 이름을 덧붙인다).
      {
        key: 'model',
        label: t('evaluation.bench.colModel'),
        categorical: true,
        groupValue: (row) => row.run.source_model || '',
        compare: (a, b) =>
          cmpText(a.run.source_model || '', b.run.source_model || ''),
        render: (row) => {
          const model = row.run.source_model;
          const via =
            row.run.source_mode === 'deployment'
              ? row.run.source_deployment
              : null;
          if (!model && !via) return <span className={cx('cell-dim')}>-</span>;
          return (
            <span className={cx('cell-model')}>
              <span className={cx('cell-model-name')}>{model || '-'}</span>
              {via && (
                <span className={cx('cell-model-via')}>
                  {t('evaluation.bench.viaDeploy', { name: via })}
                </span>
              )}
            </span>
          );
        },
      },
      // 런을 가르는 축 — 같은 벤치마크를 체크포인트 여러 개에 돌리면 여기서만 갈린다.
      // 지금 경로(배포 위임)는 평가할 체크포인트가 없어 늘 비므로, 값이 있는 옛 런이
      // 섞여 있을 때만 세운다(hasCheckpoint 주석 참조).
      ...(hasCheckpoint
        ? [
            {
              key: 'checkpoint',
              label: t('evaluation.bench.colCheckpoint'),
              categorical: true,
              groupValue: (row) => row.run.checkpoint || '',
              compare: (a, b) =>
                cmpText(a.run.checkpoint || '', b.run.checkpoint || ''),
              render: (row) =>
                row.run.checkpoint ? (
                  <span
                    className={cx('cell-checkpoint')}
                    title={row.run.checkpoint}
                  >
                    {row.run.checkpoint}
                  </span>
                ) : (
                  <span className={cx('cell-dim')}>-</span>
                ),
            },
          ]
        : []),
      {
        key: 'run',
        label: t('evaluation.bench.colRun'),
        defaultDir: 'desc',
        compare: (a, b) =>
          cmpText(a.run.create_datetime || '', b.run.create_datetime || ''),
        render: (row) => (
          <span className={cx('cell-run')}>
            {fmtDate(row.run.create_datetime)}
          </span>
        ),
      },
      {
        key: 'status',
        label: t('status.label'),
        categorical: true,
        groupValue: (row) => row.run.status,
        compare: (a, b) => cmpText(a.run.status || '', b.run.status || ''),
        render: (row) => (
          <Badge
            label={t(
              STATUS_KEYS[row.run.status] || row.run.status || 'running',
            )}
            type={STATUS_BADGE_TYPE[row.run.status] || 'gray'}
            size='sm'
          />
        ),
      },
      {
        key: 'actions',
        label: t('action.label'),
        align: 'right',
        sortable: false,
        render: (row) => (
          <span
            className={cx('cell-actions')}
            onClick={(event) => event.stopPropagation()}
          >
            {row.run.status === 'running' && (
              <ButtonV2
                type='clear'
                colorType='blue'
                size='s'
                label={t('evaluation.run.stop.action')}
                onClick={(event) => handleStopRun(row.run, event)}
              />
            )}
            <ButtonV2
              type='clear'
              colorType='red'
              size='s'
              label={t('delete.label')}
              onClick={(event) => handleDeleteRun(row.run, event)}
            />
          </span>
        ),
      },
    ],
    [
      t,
      leadColumns,
      bestRunByPair,
      hasCheckpoint,
      handleStopRun,
      handleDeleteRun,
    ],
  );

  // 결과 페이지의 '다시 실행' 은 이 화면으로 돌아와 실행 모달을 연다(설정은 프로젝트를
  // 전제로 하므로 여기가 제자리다). state 는 한 번 쓰고 지워 새로고침 때 다시 열리지 않게 한다.
  useEffect(() => {
    if (!location.state?.openRunConfig) return;
    setShowRunConfig(true);
    history.replace({ pathname: location.pathname, state: {} });
  }, [location.state, location.pathname, history]);

  const backToList = () =>
    history.push(`/user/workspace/${workspaceId}/evaluation`);
  const backToRuns = () => {
    setActiveRun(null);
    history.push(runsPath);
    fetchProject();
  };

  // "새 평가 실행" — expert 는 출력원 선택 후 세션 시작(startExpert), 정답 대조는 단일
  // 화면 모달, LLM 심사는 설정 화면(라우트)으로 간다.
  const handleNewRun = async () => {
    if (!project) return;
    if (project.eval_type === 'expert') {
      // 전문가 평가는 실추론(지연 단위 VLM)에 쓸 배포를 먼저 고른 뒤 startExpertRun으로 시작.
      setShowInferModal(true);
    } else if (project.eval_type === 'reference') {
      // 정답 대조는 단일 화면 모달 — 목록에서 벗어나지 않고 설정→실행까지 끝난다.
      setShowRunConfig(true);
    } else {
      history.push(`${runsPath}/new`);
    }
  };

  // 출력 출처 확정 후 전문가 세션 시작. 모달이 배포 | 이전 생성 런 중 **하나만** 채워 넘긴다
  // (둘 다 없으면 모달이 실행을 막고, 그래도 오면 BE 가 거절한다 — mock 폴백은 없어졌다).
  const startExpertRun = async ({
    inferencePlaygroundId,
    inferenceJobId,
    modelId,
    datasetId,
  }) => {
    setShowInferModal(false);
    if (starting) return;
    setStarting(true);
    // 채점할 모델·데이터셋은 **이 런이** 고른다(프로젝트 상속 아님).
    const body = {
      project_id: Number(projectId),
      model_id: Number(modelId),
      dataset_ids: [Number(datasetId)],
      // 출처는 화면이 고른 하나만. 둘을 함께 실으면 BE 우선순위(job > playground)가
      // 사용자의 선택을 조용히 덮는다.
      ...(inferenceJobId
        ? { inference_job_id: inferenceJobId }
        : { inference_playground_id: inferencePlaygroundId }),
    };
    const res = await startExpert(body);
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    // 결과 뷰의 authZ 경로는 런의 모델을 쓴다 — 목록 갱신 전이라 여기서 실어 준다.
    setActiveRun({ jobId: res.result.job_id, model_id: Number(modelId) });
    history.push(`${runsPath}/${res.result.job_id}`);
  };

  // 평가 추론 러너(generate) 실행 — 선택한 running 배포로 데이터셋 전량 batch 추론 후 _samples +
  // _gen_system_prompt 영속. 백그라운드 런이라 즉시 목록 갱신 후 genRunning 폴링이 완료까지 추적.
  const handleGenerate = async ({
    inference_playground_id,
    system_prompt,
    model_id,
    dataset_ids,
  }) => {
    setShowGenModal(false);
    if (generating) return;
    setGenerating(true);
    try {
      const res = await runEvalInference({
        project_id: Number(projectId),
        // 생성 런도 대상 모델·데이터셋을 스스로 지정한다(실행 시점 선택).
        model_id,
        dataset_ids,
        inference_playground_id,
        system_prompt,
      });
      if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
        errorToastMessage(res.error, res.message);
        return;
      }
      // 러너 런(running)이 목록/배너에 반영되도록 갱신하고 genRunning 폴링이 완료까지 추적.
      await fetchProject();
    } finally {
      // busy 해제는 fetchProject 반영 후에야 — 그 전엔 genRunning 이 아직 false 라 버튼이
      //   재활성되어 이중 제출될 수 있음(리뷰 HIGH). finally 로 refetch 후 해제.
      setGenerating(false);
    }
  };

  // 실행 설정 화면이 넘기는 값들. **정답 대조(BenchmarkRunConfig)와 LLM 심사(JudgeRunConfig)가
  // 같은 계약을 쓴다** — 심사 벤치마크(LogicKor)도 벤치마크 런이라 같은 엔드포인트로 나가고,
  // 심사 전용 엔드포인트는 없다. 유형별로 갈리는 건 채워 오는 필드뿐이다.
  //   benchmarks = [{ benchmark, metric }] — 한 런 = 벤치마크 하나. metric 은 서버가
  //     권장값으로 고정하므로 받기만 하고 버려진다(옛 서버 호환용으로 계속 싣는다).
  //   inferencePlaygroundId = 출력을 만들 running 배포. **필수**다 — 평가 컨테이너는 채점만
  //     하고 생성은 언제나 배포가 한다(컨테이너가 체크포인트를 직접 올리던 경로는 폐기).
  //   judgePlaygroundId = 채점을 맡길 running 배포. LLM 심사에서만 채워 온다(필수).
  //   runOptions = 심사 컨테이너 실행 옵션({ strategy?, judge_max_output_tokens? }).
  const handleBenchmarkRun = async ({
    modelId,
    datasetId,
    benchmarks,
    inferencePlaygroundId,
    judgePlaygroundId,
    runOptions,
  }) => {
    if (starting) return;
    setStarting(true);
    const res = await runBenchmark({
      project_id: Number(projectId),
      // 이 런이 평가할 모델·데이터셋 — 프로젝트가 아니라 **런**이 소유한다.
      model_id: Number(modelId),
      dataset_ids: [Number(datasetId)],
      benchmarks,
      // 출력은 언제나 빌린 배포가 만든다 — 컨테이너는 채점만 한다. 화면이 이 값을 필수로
      //   받으므로 다른 출처를 함께 싣지 않는다(BE 우선순위 inference_job_id >
      //   inference_playground_id 가 사용자의 선택을 조용히 덮는 것을 막는다).
      inference_playground_id: inferencePlaygroundId,
      // 원격 심판(LogicKor) — 서버가 배포 id 를 검증하고 OpenAI 호환 base URL 을 조립한다
      //   (URL 직접 수취는 SSRF). judge_model 과는 배타적이라 함께 보내지 않는다.
      ...(judgePlaygroundId ? { judge_playground_id: judgePlaygroundId } : {}),
      // 심사 컨테이너 실행 옵션. ⚠️ 평면으로 펼친다: BenchmarkRunBody 는 strategy·
      //   judge_max_output_tokens 를 최상위 필드로 받고 route.py 가 run_options 딕트로
      //   묶는다. run_options 로 감싸 보내면 Pydantic 이 조용히 버려 컨테이너 기본값으로 돈다.
      ...(runOptions || {}),
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setShowRunConfig(false);
    setActiveRun({
      jobId: res.result.job_id,
      status: 'running',
      // 결과 뷰의 authZ 경로용 — 목록 갱신 전이라 요청 값을 그대로 싣는다.
      model_id: Number(modelId),
    });
    // 결과 화면의 깊이는 유형마다 다르다 — 정답 대조는 독립 페이지, 심사는 상세 안.
    history.push(
      project.eval_type === 'reference'
        ? `${url}/run/${res.result.job_id}`
        : `${runsPath}/${res.result.job_id}`,
    );
  };

  const openRun = (run) => {
    if (!run?.job_id) return;
    // 정답 대조 결과는 프로젝트 상세 안이 아니라 독립 페이지다(런 하나를 깊게 읽는 화면).
    if (project.eval_type === 'reference') {
      history.push(`${url}/run/${run.job_id}`);
      return;
    }
    setActiveRun({
      jobId: run.job_id,
      status: run.status,
      model_id: run.model_id,
    });
    history.push(`${runsPath}/${run.job_id}`);
  };

  const openCompare = () => {
    history.push(comparePath);
  };

  // 비교 탭은 NavLink·직접 URL·새로고침 어느 경로로 들어와도 데이터를 조회한다.
  // 비교 가능 여부는 navList 노출로만 제어하고 Route 자체는 항상 마운트한다.
  useEffect(() => {
    if (project?.id == null || normalizedPath !== comparePath) return undefined;
    let cancelled = false;
    setCompareData(null);
    (async () => {
      const res = await compareProjectRuns(projectId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        history.replace(runsPath);
        return;
      }
      setCompareData(res.result);
    })();
    return () => {
      cancelled = true;
    };
  }, [comparePath, history, normalizedPath, project?.id, projectId, runsPath]);

  // run.metric_set 은 DB 문자열 — 벤치마크 런(정답 대조·LLM 심사)은 "benchmark:metric" CSV.
  const configSummary = (run) => {
    const raw = run.metric_set;
    if (raw == null || raw === '') return null;
    if (RUN_TABLE_TYPES.includes(project.eval_type)) {
      // metric_set = "benchmark:metric" CSV(신 스키마)를 "벤치마크 · 메트릭"으로 함께 요약.
      //   구 런은 metric-id CSV("bleu,rouge", 콜론 없음)라 metric 라벨로 폴백
      //   (BenchmarkResultView와 동일한 3단계 폴백: BENCHMARK_LABEL, 지표 이름, id).
      const parts = String(raw)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((tok) => {
          const [b, m] = tok.split(':');
          const benchLabel = BENCHMARK_LABEL[b] || metricLabel(t, b) || b;
          return m ? `${benchLabel} · ${metricLabel(t, m) || m}` : benchLabel;
        });
      return parts.length ? parts.join(', ') : null;
    }
    return null;
  };

  // ── 로딩 / 오류 ──
  if (project === null && !notFound) {
    return (
      <div className={cx('container')}>
        <div className={cx('loading-state')}>
          <Loading />
          <span>{t('evaluation.project.loading')}</span>
        </div>
      </div>
    );
  }
  if (notFound) {
    return (
      <div className={cx('container')}>
        <DetailBack
          label={t('evaluation.project.title')}
          onClick={backToList}
        />
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  const isRunsRoot =
    normalizedPath === url.replace(/\/+$/, '') || normalizedPath === runsPath;
  const backLabel = isRunsRoot
    ? t('evaluation.project.title')
    : t('evaluation.run.backToRuns');
  const goBack = isRunsRoot ? backToList : backToRuns;
  const typeLabel = t(TYPE_KEYS[project.eval_type] || project.eval_type);
  // 프로젝트는 이제 이름·유형만 잠근다 — 모델·데이터셋은 런마다 다를 수 있다. 그래서
  // 헤더는 **값이 있을 때만**(옛 프로젝트) 그 자리를 세운다. 없는 값을 '#undefined' 로
  // 찍으면 잠기지 않은 것을 잠긴 것처럼 보이게 한다.
  const modelName =
    project.model_id != null
      ? modelMap[project.model_id] || `#${project.model_id}`
      : null;
  const projectDatasetIds = project.dataset_ids || [];
  const datasetLabel = projectDatasetIds
    .map((id) => datasetMap[id] || runDatasetMap[id] || `#${id}`)
    .join(', ');
  // 상세 응답의 필드를 우선하되, 현행 목록 전용 additive 계약과 열린 화면의 최신 run으로 보강한다.
  const projectUpdateDatetime =
    project.update_datetime ||
    projectListUpdate ||
    allRuns[0]?.create_datetime ||
    project.create_datetime;
  // 실행 목록을 펼친 표로 그리는 유형(정답 대조·LLM 심사)은 목록 자체가 비교표다 —
  // 같은 값을 다른 표로 한 번 더 보여주는 '실행 비교' 탭을 두지 않는다. expert 는 목록이
  // 카드형이라 비교표가 유일한 대조 수단이므로 그대로 둔다.
  const showCompare =
    !RUN_TABLE_TYPES.includes(project.eval_type) && runs.length >= 2;
  const navList = [
    {
      label: 'evaluation.project.detail.runsTitle',
      path: runsPath,
    },
    // 비교 Route 는 항상 존재하며, 탭 노출만 위 조건으로 제어한다.
    ...(showCompare
      ? [
          {
            label: 'evaluation.project.detail.compare',
            path: comparePath,
          },
        ]
      : []),
  ];
  const topButtonList = (
    <div className={cx('top-actions')}>
      <Badge
        label={typeLabel}
        type={TYPE_BADGE_TYPE[project.eval_type] || 'gray'}
        size='sm'
      />
      <Badge
        label={t(STATUS_KEYS[project.status] || project.status)}
        type={STATUS_BADGE_TYPE[project.status] || 'gray'}
        size='sm'
      />
      {/* SimpleNav 의 topButtonList 슬롯과 같은 자리라 하우스와 같은 size='l' 을 쓴다. */}
      <ButtonV2
        type='outline'
        colorType='gray'
        size='l'
        label={
          genRunning
            ? t('evaluation.generate.running')
            : t('evaluation.generate.action')
        }
        disabled={generating || genRunning}
        isLoading={generating}
        onClick={() => setShowGenModal(true)}
      />
      {showCompare && (
        <ButtonV2
          type='outline'
          size='l'
          label={t('evaluation.project.detail.compare')}
          onClick={openCompare}
        />
      )}
      <ButtonV2
        type='solid'
        size='l'
        label={
          starting
            ? t('evaluation.running')
            : t('evaluation.project.detail.newRun')
        }
        disabled={starting}
        isLoading={starting}
        onClick={handleNewRun}
      />
    </div>
  );

  return (
    <div id='ProjectDetail' className={cx('container')}>
      <DetailBack label={backLabel} onClick={goBack} />
      <div className={cx('content')}>
        <EvaluationNav
          navList={navList}
          topButtonList={topButtonList}
          titleName={project.name}
          subTitle={modelName ? `${typeLabel} · ${modelName}` : typeLabel}
        />

        {/* 실행 결과를 해석하는 전제 메타는 별도 탭이 아니라 모든 하위 화면에서 계속 노출한다. */}
        <ContentBox title={t('evaluation.project.detail.infoTitle')}>
          <div className={cx('project-meta')}>
            {/* 데이터셋도 런이 고르므로 프로젝트에 잠긴 값이 있을 때만 세운다. */}
            {datasetLabel && (
              <div className={cx('meta-item')}>
                <span className={cx('meta-label')}>
                  {t('evaluation.project.dataset')}
                </span>
                <span className={cx('meta-value', 'dataset-value')}>
                  {datasetLabel}
                </span>
              </div>
            )}
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>
                {t('evaluation.project.creator')}
              </span>
              <span className={cx('meta-value')}>{project.creator || '-'}</span>
            </div>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>{t('createdAt.label')}</span>
              <span className={cx('meta-value')}>
                {fmtDate(project.create_datetime)}
              </span>
            </div>
            <div className={cx('meta-item')}>
              <span className={cx('meta-label')}>
                {t('lastUpdatedTime.label')}
              </span>
              <span className={cx('meta-value')}>
                {fmtDate(projectUpdateDatetime)}
              </span>
            </div>
          </div>
        </ContentBox>

        <Switch>
          <Route exact path={path}>
            <Redirect to={runsPath} />
          </Route>

          {/* 라우트는 평가 유형·run 수와 무관하게 항상 마운트한다.
              유형과 비교 가능 여부는 각 Route 내부 분기와 navList 노출로만 제어한다. */}
          {/* 정답 대조 실행 설정은 라우트가 아니라 모달이다 — 이 자리는 LLM 심사 전용이다.
              심사는 세트·대상·심판·세부 설정이 한 화면을 채워 모달에 담기지 않는다. */}
          <Route exact path={`${path}/runs/new`}>
            {project.eval_type === 'judge' ? (
              <JudgeRunConfig
                workspaceId={workspaceId}
                modelOptions={modelOptions}
                datasetOptions={datasetOptions}
                running={starting}
                onRun={handleBenchmarkRun}
              />
            ) : (
              <Redirect to={runsPath} />
            )}
          </Route>

          <Route
            exact
            path={`${path}/runs/:jobId`}
            render={({ match: runMatch }) => {
              const jobId = runMatch.params.jobId;
              const savedRun = runs.find(
                (run) => String(run.job_id) === String(jobId),
              );
              const currentRun =
                String(activeRun?.jobId) === String(jobId)
                  ? activeRun
                  : savedRun;
              // 결과·채점 API 경로의 model_id 는 authZ 바인딩이라 런의 모델이어야 한다
              //   (프로젝트 모델은 옛 프로젝트 폴백일 뿐이다).
              const runModelId = currentRun?.model_id ?? project.model_id;

              // 정답 대조 결과는 독립 페이지로 옮겼다. 이 경로로 들어온 옛 링크는 그리로 넘긴다.
              if (project.eval_type === 'reference') {
                return <Redirect to={`${url}/run/${jobId}`} />;
              }
              if (runModelId == null) {
                return <Redirect to={runsPath} />;
              }
              if (project.eval_type === 'judge') {
                return (
                  <JudgeResultView
                    modelId={runModelId}
                    jobId={jobId}
                    onComplete={fetchProject}
                  />
                );
              }
              if (project.eval_type === 'expert') {
                return (
                  <ExpertRunView
                    modelId={runModelId}
                    jobId={jobId}
                    onExit={backToRuns}
                  />
                );
              }
              return <Redirect to={runsPath} />;
            }}
          />

          <Route exact path={`${path}/runs`}>
            <section className={cx('runs')}>
              <div className={cx('runs-head')}>
                <h3 className={cx('runs-title')}>
                  {t('evaluation.project.detail.runsTitle')}
                </h3>
                <Badge label={String(runs.length)} type='blue' size='sm' />
              </div>

              {(latestInference || genRunning) && (
                <div className={cx('gen-banner')}>
                  {genRunning
                    ? t('evaluation.generate.running')
                    : t('evaluation.generate.ready')}
                </div>
              )}

              {/* 정답 대조·LLM 심사는 펼친 표 — 헤더를 누른 순서가 정렬 레벨이고, 범주형이
                  선두면 그룹 경계선이 그어진다. 앞 두 열의 뜻만 유형별로 갈린다(leadColumns).
                  expert 는 한 런에 그 축이 없어(사람이 샘플을 훑는 세션) 카드 목록을 유지한다. */}
              {RUN_TABLE_TYPES.includes(project.eval_type) ? (
                <MultiSortTable
                  columns={benchColumns}
                  rows={benchRows}
                  // 한 런이 여러 행(벤치마크 쌍마다 하나)이라 run.id 만으로는 키가 겹친다.
                  rowKey={(row) => row.key}
                  // 기본은 최근 실행순 — 레벨 0(칩에는 '기본'으로만 뜬다). 같은 런의
                  // 행끼리는 metric_set 에 적힌 순서(=고른 순서)를 지킨다.
                  baseCompare={(a, b) =>
                    String(b.run.create_datetime || '').localeCompare(
                      String(a.run.create_datetime || ''),
                    ) ||
                    b.run.id - a.run.id ||
                    a.order - b.order
                  }
                  baseSortLabel={t('evaluation.bench.sortDefault')}
                  onRowClick={(row) => openRun(row.run)}
                  emptyText='evaluation.project.detail.noRuns'
                  // 모델·체크포인트가 늘어 기본 760px 에서는 열이 서로 붙는다.
                  minWidth='900px'
                />
              ) : runs.length === 0 ? (
                <EmptyBox
                  text='evaluation.project.detail.noRuns'
                  isBox
                  customStyle={{ height: '120px' }}
                />
              ) : (
                <div className={cx('run-list')}>
                  {runs.map((run) => {
                    const summary = configSummary(run);
                    const preview = metricKeys
                      .filter((key) => run.metrics?.[key] != null)
                      .slice(0, 3);
                    return (
                      <div
                        key={run.id}
                        className={cx('run-row')}
                        onClick={() => openRun(run)}
                      >
                        <div className={cx('run-main')}>
                          <span className={cx('run-dataset')}>
                            {run.dataset_name || '-'}
                          </span>
                          {summary && (
                            <span className={cx('run-config')}>{summary}</span>
                          )}
                        </div>
                        <div className={cx('run-side')}>
                          {preview.length > 0 && (
                            <span className={cx('run-metrics')}>
                              {preview
                                .map((key) =>
                                  fmtRunMetric(key, run.metrics[key]),
                                )
                                .join(' · ')}
                            </span>
                          )}
                          <Badge
                            label={t(
                              STATUS_KEYS[run.status] ||
                                run.status ||
                                'running',
                            )}
                            type={STATUS_BADGE_TYPE[run.status] || 'gray'}
                            size='sm'
                          />
                          <span className={cx('run-date')}>
                            {fmtDate(run.create_datetime)}
                          </span>
                          <span className={cx('run-open')}>
                            {project.eval_type === 'expert'
                              ? t('evaluation.project.detail.resume')
                              : t('evaluation.project.detail.open')}
                          </span>
                          {/* 진행 중일 때만. expert 는 컨테이너가 없어 중지 대상이 아니다
                              (사람이 시간에 걸쳐 채점하는 세션이라 정당히 오래 running). */}
                          {run.status === 'running' &&
                            project.eval_type !== 'expert' && (
                              <ButtonV2
                                type='clear'
                                colorType='blue'
                                size='s'
                                label={t('evaluation.run.stop.action')}
                                onClick={(event) => handleStopRun(run, event)}
                              />
                            )}
                          <ButtonV2
                            type='clear'
                            colorType='red'
                            size='s'
                            label={t('delete.label')}
                            onClick={(event) => handleDeleteRun(run, event)}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </Route>

          <Route exact path={`${path}/compare`}>
            <section className={cx('runs')}>
              <h3 className={cx('runs-title')}>
                {t('evaluation.project.detail.compareTitle')}
              </h3>
              {compareData === null ? (
                <div className={cx('loading-state')}>
                  <Loading />
                  <span>{t('evaluation.project.loading')}</span>
                </div>
              ) : (
                <EvalComparison comparison={compareData} />
              )}
            </section>
          </Route>

          <Redirect to={runsPath} />
        </Switch>

        {/* 정답 대조 실행 설정 — 단일 화면 모달. 목록에서 벗어나지 않고 설정→실행이 끝난다. */}
        {showRunConfig && project.eval_type === 'reference' && (
          <BenchmarkRunConfig
            workspaceId={workspaceId}
            modelOptions={modelOptions}
            datasetOptions={datasetOptions}
            running={starting}
            onRun={handleBenchmarkRun}
            onClose={() => setShowRunConfig(false)}
          />
        )}
        {showInferModal && (
          <ExpertInferenceModal
            workspaceId={workspaceId}
            modelOptions={modelOptions}
            datasetOptions={datasetOptions}
            inferenceRun={latestInference}
            onConfirm={startExpertRun}
            onClose={() => setShowInferModal(false)}
          />
        )}
        {showGenModal && (
          <EvalGenerateModal
            workspaceId={workspaceId}
            modelOptions={modelOptions}
            datasetOptions={datasetOptions}
            running={generating}
            onConfirm={handleGenerate}
            onClose={() => setShowGenModal(false)}
          />
        )}
      </div>
    </div>
  );
};

export default ProjectDetail;
