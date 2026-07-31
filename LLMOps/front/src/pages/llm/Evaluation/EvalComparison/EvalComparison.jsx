import { useTranslation } from 'react-i18next';

import { Badge, ButtonV2 } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import EmptyBox from '@src/components/molecules/EmptyBox';
import GuideBox from '@src/components/molecules/GuideBox';

import { addNineHours } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalComparison.module.scss';

const cx = classNames.bind(style);

// 메트릭 값 표시 — perplexity 등 큰 수는 정수부, 0~100 스케일은 소수 2자리. (SP-5 Evaluate 와 동일)
const fmtMetric = (v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

// 전문가 평가 메트릭 키 → i18n 라벨. 헤더가 raw 키 문자열을 그대로 찍으므로 매핑.
// (신규 expert_avg_score 1~5 · 레거시 expert_pass_rate 0~100 스케일 혼재 — 라벨·포맷으로 구분.)
const METRIC_LABEL_KEYS = {
  expert_avg_score: 'evaluate.metric.expertAvgScore',
  expert_pass_rate: 'evaluate.metric.expertPassRate',
};

// 실행 상태를 조나단 Badge type으로 매핑한다.
const STATUS_BADGE_TYPE = {
  created: 'gray',
  pending: 'yellow',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};

// 스케일 혼재 구분: avg_score 는 `/5`, pass_rate 는 `%`, 그 외는 기본 포맷.
const fmtMetricValue = (k, v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  if (k === 'expert_avg_score') return `${v.toFixed(2)} / 5`;
  if (k === 'expert_pass_rate') return `${v.toFixed(2)}%`;
  return fmtMetric(v);
};

/**
 * 모델 중심 평가 이력 비교표 (§14.12) — self-metric(SP-5)·벤치마크·judge(후속) 런 누적.
 * BE `list_eval_results` 의 `{ metric_keys, best, runs }` 를 소비(llm_evaluation/llm_model 동형).
 * 벤치마크의 nested metrics 는 BE 공용 빌더가 averages 로 평탄화해 동일 flat shape 로 들어온다.
 * i18n 은 SP-5 evaluate.* 키 재사용(모드 무관 공통 표).
 *
 * `showModel`(④ 교차모델 비교) 가 true 면 선두에 모델 컬럼 추가 — run.model_name 으로
 * 어느 모델 런인지 라벨링. 단일모델(기본 false)은 기존 그대로(컬럼 없음).
 *
 * `onDelete(run)` 를 주면 행마다 삭제 버튼 컬럼을 노출(이력 관리). 미제공(교차모델 비교 등)이면
 * 컬럼 없음 — 삭제 확인/호출/재조회는 부모가 소유(표는 순수 프레젠테이션).
 */
const EvalComparison = ({ comparison, showModel = false, onDelete }) => {
  const { t } = useTranslation();
  const metricKeys = comparison?.metric_keys ?? [];
  const best = comparison?.best ?? {};
  const runs = comparison?.runs ?? [];
  const canDelete = typeof onDelete === 'function';
  const metricLabel = (k) =>
    METRIC_LABEL_KEYS[k] ? t(METRIC_LABEL_KEYS[k]) : k;

  const columns = [
    showModel && {
      name: t('evaluate.model.label'),
      selector: 'model_name',
      sortable: false,
      cell: (run) => (
        <span className={cx('model-cell')}>{run.model_name || '-'}</span>
      ),
    },
    {
      name: t('evaluate.dataset.label'),
      selector: 'dataset_name',
      sortable: false,
      cell: (run) => run.dataset_name || '-',
    },
    ...metricKeys.map((k) => ({
      name: metricLabel(k),
      selector: k,
      sortable: false,
      cell: (run) => {
        const v = run.metrics?.[k];
        const isBest = best[k] === run.id && v !== undefined;
        return (
          <span className={cx('metric-cell', isBest && 'best')}>
            {v !== undefined ? fmtMetricValue(k, v) : '-'}
            {isBest && (
              <Badge
                label={t('evaluate.best.badge')}
                type='green'
                size='sm'
              />
            )}
          </span>
        );
      },
    })),
    {
      name: t('evaluate.status.label'),
      selector: 'status',
      sortable: false,
      cell: (run) => {
        const status = run.status || 'pending';
        return (
          <Badge
            label={t(`evaluate.status.${status}`)}
            type={STATUS_BADGE_TYPE[status] || 'gray'}
            size='sm'
          />
        );
      },
    },
    {
      name: t('createdAt.label'),
      selector: 'create_datetime',
      sortable: false,
      // ProjectDetail 의 fmtDate 와 같은 앱 공통 규약(addNineHours)을 쓴다. raw 로 두면
      // 같은 run 이 "실행 목록" 탭과 이 "실행 비교" 탭에서 9시간 다르게 보인다.
      cell: (run) => addNineHours(run.create_datetime) || '-',
    },
    canDelete && {
      name: t('evaluate.action.label'),
      selector: 'action',
      sortable: false,
      cell: (run) => (
        <div className={cx('action-cell')}>
          <ButtonV2
            type='clear'
            colorType='red'
            size='s'
            label={t('evaluate.action.delete')}
            onClick={() => onDelete(run)}
          />
        </div>
      ),
    },
  ].filter(Boolean);

  if (runs.length === 0) {
    return (
      <EmptyBox
        text='evaluate.empty'
        isBox
        customStyle={{ height: '120px' }}
      />
    );
  }

  return (
    <div className={cx('comparison')}>
      <div className={cx('table-wrap')}>
        <BorderTable
          columns={columns}
          data={runs}
          loading={false}
          selectableRows={false}
          hideSearchBox
          hideButtons
          fixedHeader
          fixedHeaderScrollHeight='480px'
        />
      </div>
      <div className={cx('guide')}>
        <GuideBox
          title={t('evaluate.comparison.hint')}
          isTitleIcon
          textList={[]}
        />
      </div>
    </div>
  );
};

export default EvalComparison;
