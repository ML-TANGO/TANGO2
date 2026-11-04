import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import {
  Redirect,
  useHistory,
  useLocation,
  useRouteMatch,
} from 'react-router-dom';

import { Badge, ButtonV2, Loading } from '@jonathan/ui-react';

import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalProject } from '@src/apis/llm/evaluation';
import { loadModalComponent } from '@src/modal';
import { STATUS_SUCCESS } from '@src/network';
import { startPath } from '@src/store/modules/breadCrumb';
import { openModal } from '@src/store/modules/modal';

import { addNineHours, errorToastMessage } from '@src/utils';

import EvalReportButton from '../EvalReport/EvalReportButton';
import BenchmarkResultView from './BenchmarkResultView';
import {
  BENCHMARK_LABEL,
  BENCHMARK_MAP,
  BENCHMARK_RESULT_EVAL_TYPES,
} from './benchmarks';
import { metricLabel } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};
const STATUS_LABEL_KEY = {
  created: 'evaluation.project.status.created',
  pending: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
  failed: 'evaluation.failed',
  // 취소는 '생성됨' 이 아니다 — 도중에 멈춘 런도 끝난 벤치마크 결과를 보여 주므로 구분해 세운다.
  cancelled: 'evaluation.batch.cancelled',
};

// 벤치마크 런 결과 = 프로젝트 상세 안의 한 구획이 아니라 **독립 페이지**다.
// 런 하나를 깊게 읽는 화면이라 프로젝트 헤더·정보 카드·실행 목록이 위에 겹쳐 있으면
// 화면의 절반을 배경이 차지한다. 뒤로가기 헤더 규약은 배포 상세(DeployDetailHeader)와
// 같은 것을 쓴다 — 같은 깊이의 화면이 같은 방식으로 돌아가야 한다.
// 라우트: /user/workspace/:id/evaluation/project/:projectId/run/:runId[?benchmark=<id>]
//   benchmark — 한 런이 여러 벤치마크를 담을 때(묶음 실행이 GPU 수만큼 런을 나눈다, 설계 §14)
//   실행 요약에서 누른 벤치마크. 주면 그 벤치마크만 보인다(종전처럼 "벤치마크 하나"의 세부 화면).
const BenchmarkResultPage = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const location = useLocation();
  const { id: workspaceId, projectId, runId } = match.params;
  const focusBenchmark =
    new URLSearchParams(location.search).get('benchmark') || null;

  const [project, setProject] = useState(null); // null=로딩
  const [runs, setRuns] = useState([]);
  const [notFound, setNotFound] = useState(false);
  const [meta, setMeta] = useState(null); // 결과가 도착해야 알 수 있는 벤치마크 신원

  // 실행 로그는 새로 만들지 않는다 — 외부잡 로그 모달(external 모드)이 이미 있다.
  useEffect(() => {
    loadModalComponent('FINETUNING_SYSTEM_LOG');
  }, []);

  const fetchProject = useCallback(async () => {
    const res = await getEvalProject(projectId);
    if (res.status === STATUS_SUCCESS && res.result?.project) {
      setProject(res.result.project);
      setRuns(res.result.runs?.runs ?? []);
    } else {
      setNotFound(true);
      errorToastMessage(res.error, res.message);
    }
  }, [projectId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    fetchProject();
  }, [dispatch, fetchProject]);

  const projectPath = `/user/workspace/${workspaceId}/evaluation/project/${projectId}/runs`;

  const run = useMemo(
    () => runs.find((r) => String(r.job_id) === String(runId)) || null,
    [runs, runId],
  );

  // 결과 JSON 이 아직 없어도(진행 중) 헤더에 무엇을 재는 런인지 세운다 —
  // metric_set 이 "benchmark:metric" CSV 라 런 설정만으로 벤치마크를 알 수 있다.
  //
  // ⚠️ CSV 의 **전 토큰**을 읽는다. 화면이 만드는 런은 벤치마크 하나뿐이지만(실행 설정이
  //    라디오 단일 선택), API·레거시 런은 여러 개를 담을 수 있다. 첫 토큰만 읽던 종전엔
  //    제목이 'MMLU' 인데 아래 점수 카드·표에는 MMLU+ARC 가 뜨는 **조용한 불일치**가
  //    남았다 — 목록(ProjectDetail.benchRows)이 이미 전 토큰을 펼치는 것과 같은 규약으로
  //    맞춘다. 콜론 없는 옛 토큰은 지표 id 뿐이라 지표 라벨로 폴백한다.
  const configured = useMemo(() => {
    // 좁혀 보는 중이면 그 벤치마크 하나 — metric_set 은 255자에서 잘려 목록에 없을 수도 있다.
    if (focusBenchmark) {
      const rec = BENCHMARK_MAP[focusBenchmark]?.recommended;
      return {
        label: BENCHMARK_LABEL[focusBenchmark] || focusBenchmark,
        metricLabel: rec ? metricLabel(t, rec) || rec : null,
      };
    }
    const raw = run?.metric_set;
    if (!raw) return null;
    const tokens = String(raw)
      .split(',')
      .map((token) => token.trim())
      .filter(Boolean);
    if (!tokens.length) return null;
    const labels = [];
    const metrics = [];
    tokens.forEach((token) => {
      const [head, tail] = token.split(':');
      if (head)
        labels.push(BENCHMARK_LABEL[head] || metricLabel(t, head) || head);
      if (tail) metrics.push(metricLabel(t, tail) || tail);
    });
    const uniq = (list) => [...new Set(list)];
    return {
      label: uniq(labels).join(' · ') || null,
      metricLabel: uniq(metrics).join(' · ') || null,
    };
    // 지표 이름이 로케일을 타므로 t 가 의존성이다.
  }, [run, t, focusBenchmark]);

  // 결과 폴링 경로의 model_id 는 **authZ 바인딩**이다(BE 가 source_model_id 로 잠근다).
  //   프로젝트가 다중 모델이 된 뒤로는 프로젝트 모델이 이 런의 모델과 다를 수 있어,
  //   런의 모델을 쓴다. project.model_id 는 그 값이 없는 옛 프로젝트의 폴백일 뿐이다.
  const runModelId = run?.model_id ?? project?.model_id ?? null;

  const title =
    meta?.benchmarkLabel || configured?.label || t('evaluation.results');
  const runStatus = run?.status || 'running';

  const openRunLog = useCallback(() => {
    if (!runId) return;
    dispatch(
      openModal({
        modalType: 'FINETUNING_SYSTEM_LOG',
        modalData: {
          jobId: runId,
          manifestName: meta?.manifestName || t('evaluation.bench.runLog'),
          mode: 'external',
        },
      }),
    );
  }, [dispatch, runId, meta, t]);

  // '다시 실행' 은 이 페이지가 아니라 프로젝트 상세의 실행 모달이 소유한다 —
  // 실행 설정은 프로젝트(모델·데이터셋)를 전제로 하므로 그쪽이 제자리다.
  // 실행 요약(BenchmarkBatchPage)에서 벤치마크를 눌러 들어왔으면 뒤로가기는 그 요약이다 —
  // 요약 → 세부 → 요약 을 오가며 벤치마크를 하나씩 읽는 흐름이다. 직접 링크면 프로젝트로.
  const backTo = location.state?.from || null;
  // 런 전체 보기 — 쿼리만 걷고 돌아갈 곳(state)은 그대로 둔다.
  const showAll = useCallback(
    () =>
      history.replace({
        pathname: location.pathname,
        search: '',
        state: location.state,
      }),
    [history, location.pathname, location.state],
  );
  const goBack = () => history.push(backTo || projectPath);
  const runAgain = () =>
    history.push({ pathname: projectPath, state: { openRunConfig: true } });

  if (notFound) {
    return (
      <div className={cx('result-page')}>
        <DeployDetailHeader
          title={t('evaluation.results')}
          backLabel={t('evaluation.run.backToRuns')}
          onBack={goBack}
        />
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  if (project === null) {
    return (
      <div className={cx('result-page')}>
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.project.loading')}</span>
        </div>
      </div>
    );
  }

  // 이 페이지는 **정답 대조** 런의 독립 결과 화면이다 — 다른 유형의 런 URL 을 직접 열거나
  // 북마크로 들어오면 프로젝트 상세 안의 제 화면으로 되돌린다. ProjectDetail 의
  // runs/:jobId 가드가 정답 대조를 이리로 넘기는 것과 짝이 되는 반대 방향 가드다.
  if (!BENCHMARK_RESULT_EVAL_TYPES.includes(project.eval_type)) {
    return <Redirect to={`${projectPath}/${runId}`} />;
  }

  return (
    <div id='BenchmarkResultPage' className={cx('result-page')}>
      <DeployDetailHeader
        title={
          <span className={cx('result-title')}>
            {title}
            <Badge
              label={t(STATUS_LABEL_KEY[runStatus] || runStatus)}
              type={STATUS_BADGE_TYPE[runStatus] || 'gray'}
              size='lg'
            />
            {/* 문항 상한을 준 빠른 점검 — 전체 측정과 나란히 비교하면 안 되는 점수다. */}
            {meta?.quickLimit != null && (
              <Badge
                label={t('evaluation.bench.quickCheckShort')}
                type='yellow'
                size='lg'
              />
            )}
          </span>
        }
        backLabel={
          (backTo && location.state?.fromLabel) ||
          project.name ||
          t('evaluation.run.backToRuns')
        }
        onBack={goBack}
        right={
          <>
            {/* 리포트는 채점이 끝난 런만 — 도중 점수(partial)는 영속하지 않는 화면용 값이다. */}
            <EvalReportButton
              modelId={runModelId}
              jobId={runId}
              disabled={runStatus !== 'completed'}
            />
            <ButtonV2
              type='outline'
              colorType='gray'
              size='l'
              label={t('evaluation.bench.runLog')}
              onClick={openRunLog}
            />
            <ButtonV2
              type='solid'
              size='l'
              label={t('evaluation.bench.runAgain')}
              onClick={runAgain}
            />
          </>
        }
      />

      <p className={cx('result-meta')}>
        <span>
          {t('evaluation.project.dataset')} <em>{run?.dataset_name || '-'}</em>
        </span>
        {configured?.metricLabel && (
          <span>
            {t('evaluation.bench.representative')}{' '}
            <em>{configured.metricLabel}</em>
          </span>
        )}
        <span>
          {t('createdAt.label')}{' '}
          <em>{addNineHours(run?.create_datetime) || '-'}</em>
        </span>
      </p>

      {/* 런을 못 찾으면(지워졌거나 잘못된 URL) 잘못된 경로로 폴링하지 않는다. */}
      {runModelId == null ? (
        <EmptyBox
          text='evaluation.project.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      ) : (
        <BenchmarkResultView
          modelId={runModelId}
          jobId={runId}
          onComplete={fetchProject}
          onMeta={setMeta}
          focusBenchmark={focusBenchmark}
          onShowAll={showAll}
        />
      )}
    </div>
  );
};

export default BenchmarkResultPage;
