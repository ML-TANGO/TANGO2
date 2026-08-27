import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Checkbox, Loading } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import GuideBox from '@src/components/molecules/GuideBox';

import { formatMetricValue } from '../BenchmarkEvaluation/benchmarkMetrics';
import {
  EXPERT_METRIC_LABEL_KEYS,
  STATUS_BADGE_TYPE,
  SWATCH_COUNT,
  benchmarkLabelOf,
  buildRunMatrix,
  primaryScoreOf,
} from './compareMatrix';

import { getEvalCompareRuns, listEvalRuns } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { addNineHours, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalCrossCompare.module.scss';

const cx = classNames.bind(style);

// llm_evaluation compare-runs 상한과 일치(초과 선택을 막아 422 를 피한다).
const MAX_RUNS = 20;

// 열=런 비교(P1) — 모델 축이 못 하던 "모델 A 의 ckpt3 vs 모델 B 의 ckpt1" 을 가능하게 한다.
//   모델 축(EvalCrossCompare)은 모델별 best 를 자동으로 뽑아 특정 런을 지목할 수 없었다.
//   여기서는 후보 목록에서 런을 직접 담고, 담은 런이 그대로 열이 된다.
const EvalRunCompare = ({ workspaceId }) => {
  const { t } = useTranslation();

  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [selected, setSelected] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const reqRef = useRef(0); // 최신 비교 요청만 반영(빠른 토글 시 stale 응답 무시).
  const mountedRef = useRef(true); // 언마운트 후 도착 응답의 setState 차단.

  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  // 워크스페이스 전 평가 런(프로젝트를 가로지른다 — 그래야 프로젝트가 다른 런끼리 견준다).
  useEffect(() => {
    if (!workspaceId) {
      setLoadingRuns(false);
      return undefined;
    }
    let cancelled = false;
    setLoadingRuns(true);
    listEvalRuns(workspaceId).then((res) => {
      if (cancelled) return;
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result)
          ? res.result
          : (res.result?.runs ?? []);
        setRuns(list.filter((r) => r?.id != null));
      } else {
        errorToastMessage(res.error, res.message);
      }
      setLoadingRuns(false);
    });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const fetchCompare = useCallback(
    async (ids) => {
      if (!ids.length) {
        setComparison(null);
        return;
      }
      const reqId = ++reqRef.current;
      setLoadingCompare(true);
      try {
        const res = await getEvalCompareRuns(workspaceId, ids);
        // 언마운트됐거나 더 최신 요청이 진행 중이면 무시(stale/post-unmount).
        if (!mountedRef.current || reqId !== reqRef.current) return;
        if (res.status === STATUS_SUCCESS) {
          setComparison(res.result);
        } else {
          errorToastMessage(res.error, res.message);
        }
      } finally {
        // 최신 요청만 스피너 해제 — stale 요청이 스피너를 끄지 않도록(stuck 방지).
        if (mountedRef.current && reqId === reqRef.current) {
          setLoadingCompare(false);
        }
      }
    },
    [workspaceId],
  );

  // 점수가 없는 런은 열로 세울 값이 없다 — 담기 자체를 막고 배지로 이유를 남긴다.
  const isSelectable = (run) => run.status === 'completed';

  const toggle = (id) => {
    if (selected.includes(id)) {
      const next = selected.filter((x) => x !== id);
      setSelected(next);
      fetchCompare(next);
      return;
    }
    if (selected.length >= MAX_RUNS) {
      errorToastMessage(
        null,
        t('evaluation.compare.runCap', { max: MAX_RUNS }),
      );
      return;
    }
    const next = [...selected, id];
    setSelected(next);
    fetchCompare(next);
  };

  // 색은 **모델** 단위로 고정한다 — 열이 런이라 런마다 색을 주면 20열에서 6색이 순환해
  // 없는 묶음을 있는 것처럼 보이게 한다. 모델로 묶으면 "이 열들은 같은 모델" 이 읽힌다.
  const swatchOf = useMemo(() => {
    const map = {};
    let n = 0;
    runs.forEach((r) => {
      if (r.model_id == null || map[r.model_id]) return;
      map[r.model_id] = `sw-${n % SWATCH_COUNT}`;
      n += 1;
    });
    return map;
  }, [runs]);

  // 후보는 프로젝트로 묶는다 — 평가 프로젝트가 "모델+데이터셋+평가유형" 단위라
  // 그 안에서 고르면 사과 대 사과가 되고, 가로지르면 데이터셋 경고가 뜬다.
  const groups = useMemo(() => {
    const byProject = new Map();
    runs.forEach((run) => {
      const gid = run.eval_project_id ?? `model-${run.model_id}`;
      if (!byProject.has(gid)) {
        byProject.set(gid, {
          id: gid,
          name: run.project_name || run.model_name || '-',
          model: run.model_name || '-',
          items: [],
        });
      }
      byProject.get(gid).items.push(run);
    });
    return [...byProject.values()];
  }, [runs]);

  // t 는 행 제목·부제(지표 이름)를 만드는 데 쓰이므로 의존성이다.
  const matrix = useMemo(
    () => buildRunMatrix(comparison, t),
    [comparison, t],
  );

  const rowTitle = (row) =>
    EXPERT_METRIC_LABEL_KEYS[row.key]
      ? t(EXPERT_METRIC_LABEL_KEYS[row.key])
      : row.title;

  // "실제로 답을 만든 모델" — 위임 런이면 배포가 서빙하는 모델이라 프로젝트 모델과 다르다.
  const modelLabel = (run) => run.source_model || run.model_name || '-';

  // 체크포인트 런은 체크포인트 이름, 배포에 위임한 런은 배포 이름(체크포인트가 없다).
  const sourceLabel = (run) => {
    if (run.checkpoint) return run.checkpoint;
    if (run.source_mode === 'deployment' && run.source_deployment) {
      return t('evaluation.compare.viaDeployment', {
        name: run.source_deployment,
      });
    }
    return '-';
  };

  const scoreLabel = (run) => {
    const score = primaryScoreOf(run);
    return score ? formatMetricValue(score.metricId, score.value) : '-';
  };

  // 셀 — 열이 곧 런이라 "무엇이 이 점수를 냈나"(cell-from)는 열 머리가 이미 말한다.
  // 값이 없으면 '미실행' 이 아니라 `-` 다: 사용자가 그 런을 지목했으므로 "그 런이 그
  // 지표를 안 쟀다" 가 자연스러운 사실이다.
  const renderCell = (row, run) => {
    const cell = row.cells[run.id];
    if (!cell) {
      return <div className={cx('cell', 'empty')}>-</div>;
    }
    return (
      <div className={cx('cell', cell.isBest && 'is-best')}>
        <span className={cx('cell-value')}>
          {formatMetricValue(row.metricId, cell.value)}
        </span>
        <span className={cx('cell-delta', cell.isBest && 'best')}>
          {cell.isBest ? t('evaluate.best.badge') : cell.delta}
        </span>
        <span className={cx('cell-bar')}>
          <i
            className={cx('cell-bar-fill', swatchOf[run.model_id])}
            style={{ width: `${cell.barPercent}%` }}
          />
        </span>
      </div>
    );
  };

  const renderCandidate = (run) => {
    const selectable = isSelectable(run);
    const checked = selected.includes(run.id);
    return (
      <tr
        key={run.id}
        className={cx('cand-row', checked && 'on', !selectable && 'off')}
      >
        <td>
          <Checkbox
            label={modelLabel(run)}
            checked={checked}
            disabled={!selectable}
            onChange={() => toggle(run.id)}
          />
        </td>
        <td className={cx('mono')} title={sourceLabel(run)}>
          {sourceLabel(run)}
        </td>
        <td>{benchmarkLabelOf(run, t)}</td>
        <td className={cx('mono')}>
          {addNineHours(run.create_datetime) || '-'}
        </td>
        <td className={cx('right', 'mono')}>{scoreLabel(run)}</td>
        <td>
          <Badge
            label={t(`evaluate.status.${run.status || 'pending'}`)}
            type={STATUS_BADGE_TYPE[run.status] || 'gray'}
            size='sm'
          />
        </td>
      </tr>
    );
  };

  const renderPicker = () => (
    <div className={cx('cand-scroll')}>
      {groups.map((group) => (
        <div className={cx('cand-group')} key={group.id}>
          <div className={cx('cand-group-head')}>
            <span className={cx('cand-group-name')}>{group.name}</span>
            <span className={cx('cand-group-model')}>{group.model}</span>
          </div>
          <table className={cx('runs')}>
            <thead>
              <tr>
                <th scope='col'>{t('evaluate.model.label')}</th>
                <th scope='col'>{t('checkpoint.label')}</th>
                <th scope='col'>{t('evaluation.compare.colBenchmark')}</th>
                <th scope='col'>{t('createdAt.label')}</th>
                <th scope='col' className={cx('right')}>
                  {t('evaluation.bench.score')}
                </th>
                <th scope='col'>{t('evaluate.status.label')}</th>
              </tr>
            </thead>
            <tbody>{group.items.map(renderCandidate)}</tbody>
          </table>
        </div>
      ))}
    </div>
  );

  const datasetNames = (comparison?.datasets ?? [])
    .map((d) => d?.dataset_name)
    .filter(Boolean)
    .join(', ');

  const renderMatrix = () => {
    if (!matrix.runs.length || !matrix.rows.length) {
      return (
        <EmptyBox
          text='evaluate.empty'
          isBox
          customStyle={{ height: '120px' }}
        />
      );
    }
    return (
      <>
        {/* 프로젝트가 데이터셋을 잠그던 시절엔 없던 조건 — 비교가 프로젝트를 가로지르며
            생겼다. 차단하지 않고 경고만 한다(다른 데이터셋 비교가 무의미하진 않다). */}
        {comparison?.dataset_consistent === false && (
          <div className={cx('warn')} role='status'>
            <span className={cx('warn-text')}>
              {t('evaluation.compare.datasetMixed')}
            </span>
            {datasetNames && (
              <span className={cx('warn-list')}>{datasetNames}</span>
            )}
          </div>
        )}
        <div className={cx('matrix-scroll')}>
          <table className={cx('matrix')}>
            <thead>
              <tr>
                <th scope='col' className={cx('metric-head')}>
                  {t('evaluation.compare.colMetric')}
                </th>
                {/* 두 줄 머리 — 같은 모델의 런이 여러 열로 뜨므로 모델명만으로는 구분이
                    안 된다. 둘째 줄이 체크포인트(또는 배포)라 열이 특정 런을 가리킨다. */}
                {matrix.runs.map((run) => (
                  <th
                    key={run.id}
                    scope='col'
                    className={cx('model-head', 'run-head')}
                  >
                    <span className={cx('model-head-inner')}>
                      <i className={cx('model-rule', swatchOf[run.model_id])} />
                      <span className={cx('model-head-name')}>
                        {modelLabel(run)}
                      </span>
                      <span
                        className={cx('run-head-sub')}
                        title={sourceLabel(run)}
                      >
                        {sourceLabel(run)}
                      </span>
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.rows.map((row) => (
                <tr key={row.key}>
                  <th scope='row' className={cx('metric-cell')}>
                    <div className={cx('row-head')}>
                      <span className={cx('row-head-top')}>
                        <span className={cx('row-name')}>{rowTitle(row)}</span>
                        {/* 척도 배지 — 행마다 만점이 다르다는 표식(세로로 읽지 마라). */}
                        <span className={cx('row-scale')}>
                          {row.scaleLabel}
                        </span>
                      </span>
                      {row.subLabel && (
                        <span className={cx('row-sub')}>{row.subLabel}</span>
                      )}
                    </div>
                  </th>
                  {matrix.runs.map((run) => (
                    <td key={run.id} className={cx('model-cell')}>
                      {renderCell(row, run)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={cx('guide')}>
          <GuideBox
            title={t('evaluation.compare.scaleHint')}
            isTitleIcon
            textList={[]}
          />
        </div>
      </>
    );
  };

  return (
    <>
      <section className={cx('section')}>
        <div className={cx('section-head')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.compare.selectRuns')}
          </h3>
          <Badge
            label={`${selected.length}/${MAX_RUNS}`}
            type='blue'
            size='sm'
          />
        </div>
        {loadingRuns ? (
          <div className={cx('loading-state')}>
            <Loading />
            <span>{t('evaluation.compare.loading')}</span>
          </div>
        ) : runs.length === 0 ? (
          <EmptyBox
            text='evaluation.compare.noRuns'
            isBox
            customStyle={{ height: '120px' }}
          />
        ) : (
          <>
            {renderPicker()}
            <div className={cx('guide')}>
              <GuideBox
                title={t('evaluation.compare.runCap', { max: MAX_RUNS })}
                isTitleIcon
                textList={[]}
              />
            </div>
          </>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.compare.resultTitle')}
        </h3>
        {selected.length === 0 ? (
          <EmptyBox
            text='evaluation.compare.pickRunHint'
            isBox
            customStyle={{ height: '120px' }}
          />
        ) : loadingCompare ? (
          <div className={cx('loading-state')}>
            <Loading />
            <span>{t('evaluation.compare.loading')}</span>
          </div>
        ) : (
          renderMatrix()
        )}
      </section>
    </>
  );
};

export default EvalRunCompare;
