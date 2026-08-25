import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getEvalResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { BENCHMARK_LABEL } from './benchmarks';
import { METRIC_LABEL, barWidth, fmt, scaleMaxFor } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 40; // 약 2분(컨테이너 기동 여유)

// 결과 상태를 조나단 Badge type으로 매핑한다(프로젝트 상세와 동일 색상 체계).
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
};

// 벤치마크 run 결과 뷰(프로젝트 상세 진입). getEvalResult(modelId, jobId)를 폴링해
// 벤치마크, 메트릭, 점수 구조의 랭킹/차트/표를 표시한다.
// 완료(ready) 시 onComplete로 상위 갱신을 트리거하며 기존 폴링 가드를 유지한다.
const BenchmarkResultView = ({ modelId, jobId, status, onComplete }) => {
  const { t } = useTranslation();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const pollRef = useRef({ alive: true, timer: null });
  const completedRef = useRef(false);

  useEffect(() => {
    const ref = pollRef.current;
    ref.alive = true;
    completedRef.current = false;
    setResults(null);
    setFailed(false);
    setLoading(true);

    const startedAt = Date.now();
    const poll = () => {
      if (!ref.alive) return;
      getEvalResult(modelId, jobId).then((res) => {
        if (!ref.alive) return;
        if (res.status !== STATUS_SUCCESS) {
          setLoading(false);
          errorToastMessage(res.error, res.message);
          return;
        }
        const result = res.result || {};
        if (result.status === 'failed' || result.status === 'cancelled') {
          setLoading(false);
          setFailed(true);
          return;
        }
        if (result.ready) {
          setResults(result.metrics);
          setLoading(false);
          if (!completedRef.current) {
            completedRef.current = true;
            onComplete?.();
          }
          return;
        }
        const elapsed = Date.now() - startedAt;
        if (elapsed >= POLL_DEADLINE_MS) {
          setLoading(false);
          errorToastMessage(null, t('evaluation.poll.timeout'));
          return;
        }
        ref.timer = setTimeout(poll, pollIntervalMs(elapsed));
      });
    };
    poll();

    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
  }, [modelId, jobId, t, onComplete]);

  // 결과를 벤치마크별 행 {key, label, metric, score}으로 변환한다. 신 스키마 우선,
  // 없으면 averages의 key별 점수로 폴백해 구 실행 결과도 유지한다.
  const rows = useMemo(() => {
    if (!results) return [];
    if (Array.isArray(results.results) && results.results.length) {
      return results.results.map((result) => ({
        key: result.benchmark,
        label: BENCHMARK_LABEL[result.benchmark] || result.benchmark,
        metric: METRIC_LABEL[result.metric] || result.metric,
        score: result.score,
        // 막대 폭 환산 척도 — 심판 점수(1~10)는 100 기준이 아니라 8.1 을 8% 로
        // 그리면 안 된다. 미등록 메트릭은 100(기존 동작).
        scaleMax: scaleMaxFor(result.metric),
      }));
    }
    const averages = results.averages || {};
    const metricMap = results.metric_map || {};
    return Object.keys(averages).map((key) => ({
      key,
      label: BENCHMARK_LABEL[key] || METRIC_LABEL[key] || key,
      metric: metricMap[key]
        ? METRIC_LABEL[metricMap[key]] || metricMap[key]
        : null,
      score: averages[key],
      scaleMax: scaleMaxFor(metricMap[key]),
    }));
  }, [results]);

  // LogicKor 상세 — 영역(6) × 턴(2) 격자. 벤치마크 계약(results[])은 대표 스칼라 1개만
  // 담으므로, 영역별 강약점은 채점기가 metrics JSON 의 'logickor' 키에 따로 실어 보낸다.
  // 이 키가 없는 런(기존 9벤치마크·구 실행)은 이 섹션이 그냥 렌더되지 않는다.
  const logickor = useMemo(() => {
    const detail = results?.logickor;
    if (!detail || !Array.isArray(detail.categories) || !detail.categories.length) {
      return null;
    }
    return detail;
  }, [results]);

  // 채점기가 실어 보낸 척도(기본 10). 막대·레이더·"만점" 문구가 같은 값을 쓴다.
  const logickorScaleMax = logickor?.scale_max || 10;

  // MixATIS 상세 — 의도·슬롯이 서로 다른 단위(발화 / 항목 / 쌍)로 채점되므로 대표
  // 스칼라(joint_acc) 하나로는 "의도는 되는데 슬롯이 안 되는" 상태를 구분할 수 없다.
  // 그래서 채점기가 metrics JSON 의 'mixatis' 키에 네 지표를 함께 실어 보내고
  // (evaluate_intent scoring.aggregate), 화면은 소스 모듈 콘솔과 같은 4칸으로 세운다.
  // 이 키가 없는 런(mock·LogicKor)은 섹션이 렌더되지 않는다.
  const mixatis = useMemo(() => {
    const detail = results?.mixatis;
    if (!detail || typeof detail.joint_acc !== 'number') return null;
    return detail;
  }, [results]);

  // 상세 패널이 있는 런은 랭킹·차트·결과표를 감춘다 — 벤치마크가 하나뿐이라 같은 값을
  // 세 번 반복하게 된다(LogicKor 에서 같은 이유로 도입한 규칙).
  const hasDetailPanel = Boolean(logickor || mixatis);

  // MixATIS 실행 근거 — 0.2.0 부터 채점기가 평가 전에 UGEN 형식을 학습하므로, 점수는
  // "체크포인트 단독"이 아니라 "체크포인트 + 그 레시피"의 값이다. 어떤 레시피였는지를
  // 점수 옆에 세우지 않으면 런끼리 비교할 근거가 없어진다.
  // empty_slot_predictions 는 형식을 어겨 파싱이 빈 예측을 만든 수라, 0 이 아니면
  // 점수를 조용히 끌어내린 양이므로 경고 톤으로 세운다(LogicKor unscored 와 같은 이유).
  const mixProvenance = useMemo(() => {
    if (!mixatis) return [];
    const train = results?.train || {};
    const evaluate = results?.evaluate || {};
    const items = [];
    if (results?.checkpoint?.name) {
      items.push({
        key: 'checkpoint',
        label: t('evaluation.bench.provCheckpoint'),
        value: results.checkpoint.name,
      });
    }
    items.push({
      key: 'train',
      label: t('evaluation.bench.mixTrainLabel'),
      value: train.trained
        ? t('evaluation.bench.mixTrainOn', {
            examples: train.examples,
            epochs: train.epochs,
          })
        : t('evaluation.bench.mixTrainOff'),
      warn: !train.trained,
    });
    const empty =
      (evaluate.empty_slot_predictions || 0) +
      (evaluate.empty_intent_predictions || 0);
    if (empty > 0) {
      items.push({
        key: 'empty',
        label: t('evaluation.bench.mixEmptyLabel'),
        value: t('evaluation.bench.mixEmptyValue', { count: empty }),
        warn: true,
      });
    }
    return items;
  }, [mixatis, results, t]);

  // 실행 근거 — "이 점수가 어느 체크포인트·어느 심판에서 나왔나". 채점 컨테이너가
  // metrics 에 새겨 보내는 값을 그대로 읽는다(evaluate_logickor_judge app.py 의
  // metrics.checkpoint / judge / generate). 대표 스칼라 하나만 놓고 체크포인트끼리
  // 비교하면 무엇을 비교한 건지 알 수 없어서, 점수 옆에 근거를 같이 세운다.
  // ⚠️ checkpoint.path 는 NFS 실경로라 화면에 올리지 않는다 — 컨테이너에 넘기는 것도
  //    이름 한 조각뿐이고(service.run_benchmark), 경로는 응답·로그로 새면 안 되는 값이다.
  // unscored/skipped/empty_rows 는 0 이 아니면 평균을 조용히 끌어내린 양이라 경고 톤으로
  // 세운다(컨테이너도 같은 이유로 이 셋을 metrics 에 남긴다).
  const provenance = useMemo(() => {
    if (!results) return [];
    const judge = results.judge || {};
    const generate = results.generate || {};
    const items = [];
    if (results.checkpoint?.name) {
      items.push({
        key: 'checkpoint',
        label: t('evaluation.bench.provCheckpoint'),
        value: results.checkpoint.name,
      });
    }
    if (judge.model) {
      items.push({
        key: 'judge',
        label: t('evaluation.bench.provJudge'),
        value: judge.model,
      });
    }
    if (Number.isFinite(Number(judge.judged))) {
      items.push({
        key: 'judged',
        label: t('evaluation.bench.provJudged'),
        value: String(judge.judged),
      });
    }
    if (Number(judge.unscored) > 0) {
      items.push({
        key: 'unscored',
        label: t('evaluation.bench.provUnscored'),
        value: String(judge.unscored),
        warn: true,
      });
    }
    if (Number(judge.skipped) > 0) {
      items.push({
        key: 'skipped',
        label: t('evaluation.bench.provSkipped'),
        value: String(judge.skipped),
        warn: true,
      });
    }
    if (Number(generate.empty_rows) > 0) {
      items.push({
        key: 'empty_rows',
        label: t('evaluation.bench.provEmptyRows'),
        value: String(generate.empty_rows),
        warn: true,
      });
    }
    return items;
  }, [results, t]);

  // 표 = 영역 행 + 종합 행 1개. 소스 콘솔도 tbody 마지막에 종합을 덧붙여 영역과 전체를
  // 한 표에서 비교하게 한다. isTotal 로 셀 렌더러가 구분한다.
  const logickorRows = useMemo(() => {
    if (!logickor) return [];
    return [
      ...logickor.categories,
      {
        category: t('evaluation.bench.totalRow'),
        single: logickor.single_turn,
        multi: logickor.multi_turn,
        overall: logickor.overall,
        isTotal: true,
      },
    ];
  }, [logickor, t]);

  const logickorColumns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colCategory'),
        selector: 'category',
        sortable: false,
        cell: (row) => (
          <span className={cx(row.isTotal ? 'total-label' : 'table-label')}>
            {row.category}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.turnSingle'),
        selector: 'single',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score', 'turn-single')}>
            {fmt2(row.single)}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.turnMulti'),
        selector: 'multi',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score', 'turn-multi')}>
            {fmt2(row.multi)}
          </span>
        ),
      },
      {
        // 2턴 − 1턴. 후속 질문에서 무너지는지(음수) 버티는지(양수)가 이 벤치마크의 관전
        // 지점이라 소스도 별 열로 뽑아 부호째 보여준다.
        name: t('evaluation.bench.colDiff'),
        selector: 'diff',
        sortable: false,
        cell: (row) => (
          <span className={cx('diff-value', diffTone(row.multi, row.single))}>
            {diffText(row.multi, row.single)}
          </span>
        ),
      },
      {
        name: t('evaluation.bench.colVerdict'),
        selector: 'verdict',
        sortable: false,
        cell: (row) => {
          // 종합 행은 등급이 아니라 대표 스칼라 그 자체 — 배지로 감싸면 영역 등급과
          // 같은 종류로 읽히므로 숫자만 놓는다.
          if (row.isTotal) {
            return <span className={cx('table-score')}>{fmt2(row.overall)}</span>;
          }
          const verdict = judgeVerdict(
            (Number(row.single) + Number(row.multi)) / 2,
          );
          if (!verdict) return '-';
          return (
            <Badge
              label={t(`evaluation.bench.verdict.${verdict.key}`)}
              type={verdict.badge}
              size='sm'
            />
          );
        },
      },
    ],
    [t],
  );

  const ranking = useMemo(
    () =>
      rows
        .filter((row) => Number.isFinite(Number(row.score)))
        .sort((a, b) => Number(b.score) - Number(a.score)),
    [rows],
  );

  const columns = useMemo(
    () => [
      {
        name: t('evaluation.bench.colBenchShort'),
        selector: 'label',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-label')}>{row.label}</span>
        ),
      },
      {
        name: t('evaluation.metric'),
        selector: 'metric',
        sortable: false,
        cell: (row) => row.metric || '-',
      },
      {
        name: t('evaluation.bench.score'),
        selector: 'score',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{fmt(row.score)}</span>
        ),
      },
    ],
    [t],
  );

  const resultStatus = failed
    ? 'failed'
    : results
      ? 'completed'
      : status || 'running';
  const statusLabel = t(STATUS_LABEL_KEY[resultStatus] || resultStatus);

  const statusBadge = (
    <div className={cx('result-status')}>
      <Badge
        label={statusLabel}
        type={STATUS_BADGE_TYPE[resultStatus] || 'gray'}
        size='sm'
      />
    </div>
  );

  if (failed) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.failed'
          isBox
          isRed
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }
  if (loading && !results) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.running')}</span>
        </div>
      </div>
    );
  }
  if (!results || rows.length === 0) {
    return (
      <div className={cx('benchmark-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.poll.timeout'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  return (
    <div className={cx('benchmark-result')}>
      {statusBadge}

      {ranking.length > 0 && (
        <section className={cx('result-section')}>
          <div className={cx('result-section-head')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.bench.resultRanking')}
            </h3>
            {results.mock && <Badge label='mock' type='gray' size='sm' />}
          </div>
          <div className={cx('score-grid')}>
            {ranking.map((row, index) => (
              <div key={row.key} className={cx('score-card')}>
                <Badge label={`#${index + 1}`} type='blue' size='sm' />
                <div className={cx('score-metric')}>{row.label}</div>
                {row.metric && (
                  <div className={cx('score-sub')}>{row.metric}</div>
                )}
                <div className={cx('score-value')}>{fmt(row.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {!hasDetailPanel && ranking.length > 0 && (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.bench.resultChart')}
          </h3>
          <div className={cx('chart-wrap')}>
            {ranking.map((row) => (
              <div key={row.key} className={cx('chart-row')}>
                <div className={cx('chart-label')}>{row.label}</div>
                <div className={cx('chart-bar-wrap')}>
                  <div
                    className={cx('chart-bar')}
                    style={{ width: `${barWidth(row.score, row.scaleMax)}%` }}
                  />
                </div>
                <div className={cx('chart-value')}>{fmt(row.score)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* LogicKor 상세 — 소스 모듈 웹 콘솔(Evaluation/Logickor_web/web)의 결과 패널과
          같은 구성: 스코어카드 3장(1턴/2턴/종합) → 영역별 1턴·2턴 막대 + 영역 레이더 →
          차이·평가까지 담은 표(마지막 행 = 종합). 영역별 강약점이 이 벤치마크의 핵심
          정보라서(대표 스칼라 하나로는 "어디가 약한지"를 알 수 없다) 소스도 같은 순서로
          쌓아 올린다. 다른 벤치마크 런에는 이 키가 없어 섹션이 렌더되지 않는다. */}
      {logickor && (
        <section className={cx('result-section')}>
          <div className={cx('result-section-head')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.bench.logickorTitle')}
            </h3>
            <Badge
              label={t('evaluation.bench.logickorMeta', {
                count: logickor.count,
                max: fmt(logickorScaleMax),
              })}
              type='gray'
              size='sm'
            />
          </div>

          {provenance.length > 0 && (
            <ul className={cx('provenance')}>
              {provenance.map((item) => (
                <li
                  key={item.key}
                  className={cx('provenance-item', item.warn && 'warn')}
                >
                  <span className={cx('provenance-label')}>{item.label}</span>
                  <span className={cx('provenance-value')}>{item.value}</span>
                </li>
              ))}
            </ul>
          )}

          <div className={cx('score-grid')}>
            <div className={cx('score-card')}>
              <div className={cx('score-metric')}>
                {t('evaluation.bench.turnSingle')}
              </div>
              <div className={cx('score-value', 'turn-single')}>
                {fmt2(logickor.single_turn)}
              </div>
              <div className={cx('score-unit')}>
                {t('evaluation.bench.unitOutOf', { max: fmt(logickorScaleMax) })}
              </div>
            </div>
            <div className={cx('score-card')}>
              <div className={cx('score-metric')}>
                {t('evaluation.bench.turnMulti')}
              </div>
              <div className={cx('score-value', 'turn-multi')}>
                {fmt2(logickor.multi_turn)}
              </div>
              <div className={cx('score-unit')}>
                {t('evaluation.bench.unitOutOf', { max: fmt(logickorScaleMax) })}
              </div>
            </div>
            {/* 종합만 강조 — 이력·교차비교에 실리는 대표 스칼라가 이 값이다. */}
            <div className={cx('score-card', 'accent')}>
              <div className={cx('score-metric')}>
                {t('evaluation.bench.turnOverall')}
              </div>
              <div className={cx('score-value')}>{fmt2(logickor.overall)}</div>
              <div className={cx('score-unit')}>
                {t('evaluation.bench.unitOverall')}
              </div>
            </div>
          </div>

          <div className={cx('logickor-charts')}>
            <div className={cx('chart-wrap')}>
              <h4 className={cx('chart-subtitle')}>
                {t('evaluation.bench.catChartTitle')}
              </h4>
              <div className={cx('cat-rows')}>
                {logickor.categories.map((row) => (
                  <div key={row.category} className={cx('cat-row')}>
                    <div className={cx('cat-name')}>{row.category}</div>
                    {[
                      ['single', row.single],
                      ['multi', row.multi],
                    ].map(([turn, score]) => (
                      <div key={turn} className={cx('cat-track')}>
                        <span className={cx('cat-tag')}>
                          {turn === 'single' ? 'S' : 'M'}
                        </span>
                        <div className={cx('cat-rail')}>
                          <div
                            className={cx('cat-fill', turn)}
                            style={{
                              width: `${barWidth(score, logickorScaleMax)}%`,
                            }}
                          />
                        </div>
                        <span
                          className={cx('cat-value', `turn-${turn}`)}
                        >
                          {fmt2(score)}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className={cx('chart-wrap')}>
              <h4 className={cx('chart-subtitle')}>
                {t('evaluation.bench.radarTitle')}
              </h4>
              <div className={cx('radar-wrap')}>
                <LogicKorRadar
                  categories={logickor.categories}
                  scaleMax={logickorScaleMax}
                />
                <div className={cx('radar-legend')}>
                  <span className={cx('radar-legend-item')}>
                    <i className={cx('radar-swatch', 'single')} />
                    {t('evaluation.bench.turnSingle')}
                  </span>
                  <span className={cx('radar-legend-item')}>
                    <i className={cx('radar-swatch', 'multi')} />
                    {t('evaluation.bench.turnMulti')}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className={cx('result-table')}>
            {/* 영역 수가 고정(6 + 종합)이라 페이지네이션이 의미가 없다. BorderTable 은
                pagination={!fixedHeader} 이므로 fixedHeader 로 페이저를 끈다. */}
            <BorderTable
              columns={logickorColumns}
              data={logickorRows}
              loading={false}
              selectableRows={false}
              hideSearchBox
              hideButtons
              fixedHeader
              fixedHeaderScrollHeight='420px'
            />
          </div>
        </section>
      )}

      {/* MixATIS 상세 — 소스 모듈 웹 콘솔(Evaluation/Intent_web/web_app.py)의 지표 카드와
          같은 구성: Intent Acc / Intent F1(+P·R) / Slot F1(+P·R) / Overall (Joint) Acc.
          네 지표를 함께 세우는 이유는 단위가 서로 다르기 때문이다 — Intent Acc 는 발화
          단위 완전일치, F1 은 항목·쌍 단위 부분점수, Joint 는 의도·슬롯 동시 완전일치다.
          Joint 하나만 보면 "의도는 90% 인데 슬롯 경계가 밀린" 상태를 구분할 수 없다. */}
      {mixatis && (
        <section className={cx('result-section')}>
          <div className={cx('result-section-head')}>
            <h3 className={cx('result-section-title')}>
              {t('evaluation.bench.mixatisTitle')}
            </h3>
            <Badge
              label={t('evaluation.bench.mixatisMeta', {
                count: mixatis.count,
              })}
              type='gray'
              size='sm'
            />
          </div>

          {mixProvenance.length > 0 && (
            <ul className={cx('provenance')}>
              {mixProvenance.map((item) => (
                <li
                  key={item.key}
                  className={cx('provenance-item', item.warn && 'warn')}
                >
                  <span className={cx('provenance-label')}>{item.label}</span>
                  <span className={cx('provenance-value')}>{item.value}</span>
                </li>
              ))}
            </ul>
          )}

          <div className={cx('score-grid')}>
            <div className={cx('score-card')}>
              <div className={cx('score-metric')}>Intent Acc</div>
              <div className={cx('score-value', 'turn-single')}>
                {pct(mixatis.intent?.acc)}
              </div>
              <div className={cx('score-unit')}>
                {t('evaluation.bench.mixIntentAccDesc')}
              </div>
            </div>
            <div className={cx('score-card')}>
              <div className={cx('score-metric')}>Intent F1</div>
              <div className={cx('score-value')}>{pct(mixatis.intent?.f1)}</div>
              <div className={cx('score-sub')}>
                {`P ${pct(mixatis.intent?.precision)} · R ${pct(mixatis.intent?.recall)}`}
              </div>
            </div>
            <div className={cx('score-card')}>
              <div className={cx('score-metric')}>Slot F1</div>
              <div className={cx('score-value')}>{pct(mixatis.slot?.f1)}</div>
              <div className={cx('score-sub')}>
                {`P ${pct(mixatis.slot?.precision)} · R ${pct(mixatis.slot?.recall)}`}
              </div>
            </div>
            {/* 대표 스칼라 — 이력·교차비교에 실리는 값이 이것이라 강조한다. */}
            <div className={cx('score-card', 'accent')}>
              <div className={cx('score-metric')}>Overall (Joint) Acc</div>
              <div className={cx('score-value')}>{pct(mixatis.joint_acc)}</div>
              <div className={cx('score-unit')}>
                {t('evaluation.bench.mixJointDesc')}
              </div>
            </div>
          </div>
        </section>
      )}

      {!hasDetailPanel && (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.results')}
          </h3>
          <div className={cx('result-table')}>
            <BorderTable
              columns={columns}
              data={rows}
              loading={false}
              selectableRows={false}
              hideSearchBox
              hideButtons
              fixedHeader
              fixedHeaderScrollHeight='480px'
            />
          </div>
        </section>
      )}
    </div>
  );
};

export default BenchmarkResultView;
