import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import { Badge, Loading } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import GuideBox from '@src/components/molecules/GuideBox';
import Tab from '@src/components/molecules/Tab';

import { formatMetricValue } from '../BenchmarkEvaluation/benchmarkMetrics';
import EvalRunCompare from './EvalRunCompare';
import {
  EXPERT_METRIC_LABEL_KEYS,
  STATUS_BADGE_TYPE,
  SWATCH_COUNT,
  buildMatrix,
} from './compareMatrix';

import { getEvalCompare } from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { addNineHours, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalCrossCompare.module.scss';

const cx = classNames.bind(style);

const MAX_MODELS = 6; // llm_evaluation MAX_COMPARE_MODELS 와 일치(초과 시 BE 422 회피).

// 비교 축. 모델 축(기존)은 모델별 best 를 자동으로 뽑아 "어느 모델이 제일 낫나" 에 답하고,
// 런 축(P1)은 사용자가 지목한 런을 그대로 열로 세워 "ckpt3 vs ckpt1" 에 답한다. 묻는 질문이
// 다르므로 둘 다 남긴다.
const MODE_MODEL = 'model';
const MODE_RUN = 'run';
const MODE_OPTIONS = [
  { label: 'evaluation.compare.modeModel', value: MODE_MODEL },
  { label: 'evaluation.compare.modeRun', value: MODE_RUN },
];

// 교차모델 비교(④, §14.12) — **행=지표 · 열=모델** 행렬. 묻는 질문이 "이 벤치마크에서 어느
//   모델이 제일 낫나" 라서 모델을 열로 세운다(런을 행으로 늘어놓으면 같은 모델의 행이
//   흩어져 모델이 늘수록 읽기 어렵다). 셀은 그 모델의 그 지표 최고 런 하나만 세우고,
//   나머지 런은 행 펼침으로 내린다. 런 생성 X — 읽기 전용 비교.
const EvalCrossCompare = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [mode, setMode] = useState(MODE_MODEL);
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [selected, setSelected] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [openRows, setOpenRows] = useState({}); // metric_key → 펼침 여부
  const reqRef = useRef(0); // 최신 비교 요청만 반영(빠른 토글 시 stale 응답 무시).
  const mountedRef = useRef(true); // 언마운트 후 도착 응답의 setState 차단.

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
  }, [dispatch]);

  // 언마운트 시 in-flight 비교 응답이 setState 하지 않도록 차단(codex).
  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  // 워크스페이스 학습완료 모델 목록(ModelSelector 와 동일 소스).
  useEffect(() => {
    if (!workspaceId) {
      setLoadingModels(false);
      return;
    }
    let cancelled = false;
    setLoadingModels(true);
    callApi({ url: `models?workspace_id=${workspaceId}`, method: 'GET' }).then(
      (res) => {
        if (cancelled) return;
        if (res.status === STATUS_SUCCESS) {
          const list = Array.isArray(res.result)
            ? res.result
            : (res.result?.list ?? []);
          setModels(list.filter((m) => m.id != null));
        } else {
          errorToastMessage(res.error, res.message);
        }
        setLoadingModels(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const fetchCompare = useCallback(async (ids) => {
    if (!ids.length) {
      setComparison(null);
      return;
    }
    const reqId = ++reqRef.current;
    setLoadingCompare(true);
    try {
      const res = await getEvalCompare(ids);
      // 언마운트됐거나 더 최신 요청이 진행 중이면 무시(stale/post-unmount).
      if (!mountedRef.current || reqId !== reqRef.current) return;
      if (res.status === STATUS_SUCCESS) {
        setComparison(res.result);
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      // 최신 요청만 스피너 해제 — stale 요청이 진행 중 스피너를 끄지 않도록(stuck 방지).
      if (mountedRef.current && reqId === reqRef.current) {
        setLoadingCompare(false);
      }
    }
  }, []);

  const toggle = (id) => {
    if (selected.includes(id)) {
      const next = selected.filter((x) => x !== id);
      setSelected(next);
      fetchCompare(next);
      return;
    }
    if (selected.length >= MAX_MODELS) {
      errorToastMessage(
        null,
        t('evaluation.compare.modelCap', { max: MAX_MODELS }),
      );
      return;
    }
    const next = [...selected, id];
    setSelected(next);
    fetchCompare(next);
  };

  const toggleRow = (key) =>
    setOpenRows((prev) => ({ ...prev, [key]: !prev[key] }));

  // 모델 색은 목록 순서로 고정한다 — 선택을 바꿔도 같은 모델이 같은 색을 유지해야
  // 칩·열 머리·펼침 목록의 점이 서로를 가리킬 수 있다.
  const swatchOf = useMemo(() => {
    const map = {};
    models.forEach((m, i) => {
      map[m.id] = `sw-${i % SWATCH_COUNT}`;
    });
    return map;
  }, [models]);

  // t 는 행 제목·부제(지표 이름)를 만드는 데 쓰이므로 의존성이다.
  const matrix = useMemo(() => buildMatrix(comparison, t), [comparison, t]);

  const rowTitle = (row) =>
    EXPERT_METRIC_LABEL_KEYS[row.key]
      ? t(EXPERT_METRIC_LABEL_KEYS[row.key])
      : row.title;

  // 셀·펼침 목록의 "무엇이 이 점수를 냈나". 체크포인트 런은 체크포인트 이름, 배포에 위임한
  // 런은 배포 이름(체크포인트가 없다).
  const sourceLabel = (run) => {
    if (run.checkpoint) return run.checkpoint;
    if (run.source_mode === 'deployment' && run.source_deployment) {
      return t('evaluation.compare.viaDeployment', {
        name: run.source_deployment,
      });
    }
    return '-';
  };

  const renderCell = (row, model) => {
    const cell = row.cells[model.id];
    if (!cell) {
      return (
        <div className={cx('cell', 'empty')}>
          {t('evaluation.compare.notRun')}
        </div>
      );
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
            className={cx('cell-bar-fill', swatchOf[model.id])}
            style={{ width: `${cell.barPercent}%` }}
          />
        </span>
        <span className={cx('cell-from')} title={sourceLabel(cell.run)}>
          {sourceLabel(cell.run)}
        </span>
      </div>
    );
  };

  // 펼침 버튼(aria-controls) ↔ 드로어 행(id) 을 잇는 id. 지표 키가 그대로 id 가 되면
  // 안전하지 않은 문자가 섞일 수 있어 단어 문자 외에는 '-' 로 바꾼다.
  const drawerId = (key) => `xcmp-runs-${String(key).replace(/\W+/g, '-')}`;

  // 펼침 한 줄 — 그 지표에 기여한 런 하나. 모델 열은 "실제로 답을 만든 모델"이라
  // 위임 런이면 배포가 서빙하는 모델명이 온다(프로젝트 모델과 다를 수 있다).
  const renderRunRow = (row, run) => (
    <tr key={run.id}>
      <td>
        <i className={cx('run-dot', swatchOf[run.model_id])} />
        {run.source_model || run.model_name || '-'}
      </td>
      <td className={cx('mono')}>{sourceLabel(run)}</td>
      <td className={cx('mono')}>{addNineHours(run.create_datetime) || '-'}</td>
      <td className={cx('right', 'mono')}>
        {formatMetricValue(row.metricId, run.metrics[row.key])}
      </td>
      <td>
        <Badge
          label={t(`evaluate.status.${run.status || 'pending'}`)}
          type={STATUS_BADGE_TYPE[run.status] || 'gray'}
          size='sm'
        />
      </td>
    </tr>
  );

  const renderDrawer = (row, colSpan) => (
    <tr
      key={`${row.key}-runs`}
      id={drawerId(row.key)}
      className={cx('drawer')}
    >
      <td colSpan={colSpan}>
        <div className={cx('drawer-inner')}>
          <h4 className={cx('drawer-title')}>
            {t('evaluation.compare.runsTitle')}
          </h4>
          <table className={cx('runs')}>
            <thead>
              <tr>
                <th scope='col'>{t('evaluate.model.label')}</th>
                <th scope='col'>{t('checkpoint.label')}</th>
                <th scope='col'>{t('createdAt.label')}</th>
                <th scope='col' className={cx('right')}>
                  {t('evaluation.bench.score')}
                </th>
                <th scope='col'>{t('evaluate.status.label')}</th>
              </tr>
            </thead>
            <tbody>{row.runs.map((run) => renderRunRow(row, run))}</tbody>
          </table>
        </div>
      </td>
    </tr>
  );

  const renderRowHead = (row, open) => (
    <th scope='row' className={cx('metric-cell')}>
      <div className={cx('row-head')}>
        <span className={cx('row-head-top')}>
          <span className={cx('row-name')}>{rowTitle(row)}</span>
          {/* 척도 배지 — 행마다 만점이 다르다는 표식. 세로로 읽으면 안 된다는 뜻이다. */}
          <span className={cx('row-scale')}>{row.scaleLabel}</span>
        </span>
        {row.subLabel && <span className={cx('row-sub')}>{row.subLabel}</span>}
        <button
          type='button'
          className={cx('row-expand')}
          aria-expanded={open}
          // 접힌 상태에서는 드로어 행 자체가 렌더되지 않는다 — 없는 id 를 가리키면
          // 끊어진 IDREF 가 되므로 펼쳤을 때만 건다(상태는 aria-expanded 가 말한다).
          aria-controls={open ? drawerId(row.key) : undefined}
          onClick={() => toggleRow(row.key)}
        >
          {t(
            open
              ? 'evaluation.compare.collapseRuns'
              : 'evaluation.compare.expandRuns',
            { n: row.runs.length },
          )}
        </button>
      </div>
    </th>
  );

  const renderMatrix = () => {
    if (!matrix.models.length || !matrix.rows.length) {
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
        <div className={cx('matrix-scroll')}>
          <table className={cx('matrix')}>
            <thead>
              <tr>
                <th scope='col' className={cx('metric-head')}>
                  {t('evaluation.compare.colMetric')}
                </th>
                {matrix.models.map((m) => (
                  <th key={m.id} scope='col' className={cx('model-head')}>
                    <span className={cx('model-head-inner')}>
                      <i className={cx('model-rule', swatchOf[m.id])} />
                      <span className={cx('model-head-name')}>{m.name}</span>
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.rows.map((row) => {
                const open = !!openRows[row.key];
                return [
                  <tr key={row.key}>
                    {renderRowHead(row, open)}
                    {matrix.models.map((m) => (
                      <td key={m.id} className={cx('model-cell')}>
                        {renderCell(row, m)}
                      </td>
                    ))}
                  </tr>,
                  open && renderDrawer(row, matrix.models.length + 1),
                ];
              })}
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
    <div className={cx('cross-compare')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>{t('evaluation.compare.title')}</h1>
      </div>

      <div className={cx('mode-bar')}>
        <Tab
          type='c'
          sidePaddingNone
          option={MODE_OPTIONS}
          select={{ value: mode }}
          tabHandler={({ value }) => setMode(value)}
        />
      </div>

      {mode === MODE_RUN ? (
        <EvalRunCompare workspaceId={workspaceId} />
      ) : (
        <>
          <section className={cx('section')}>
            <div className={cx('section-head')}>
              <h3 className={cx('section-title')}>
                {t('evaluation.compare.selectModels')}
              </h3>
              <Badge
                label={`${selected.length}/${MAX_MODELS}`}
                type='blue'
                size='sm'
              />
            </div>
            {loadingModels ? (
              <div className={cx('loading-state')}>
                <Loading />
                <span>{t('evaluation.compare.loading')}</span>
              </div>
            ) : models.length === 0 ? (
              <EmptyBox
                text='evaluation.compare.noModels'
                isBox
                customStyle={{ height: '120px' }}
              />
            ) : (
              <>
                <div className={cx('model-chips')}>
                  {models.map((m) => {
                    const checked = selected.includes(m.id);
                    return (
                      <button
                        type='button'
                        key={m.id}
                        className={cx('chip', checked && 'on')}
                        aria-pressed={checked}
                        onClick={() => toggle(m.id)}
                      >
                        <i
                          className={cx('chip-swatch', checked && swatchOf[m.id])}
                        />
                        {m.name}
                        <span className={cx('chip-id')}>{`#${m.id}`}</span>
                      </button>
                    );
                  })}
                </div>
                <div className={cx('guide')}>
                  <GuideBox
                    title={t('evaluation.compare.modelCap', {
                      max: MAX_MODELS,
                    })}
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
                text='evaluation.compare.pickHint'
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
      )}
    </div>
  );
};

export default EvalCrossCompare;
