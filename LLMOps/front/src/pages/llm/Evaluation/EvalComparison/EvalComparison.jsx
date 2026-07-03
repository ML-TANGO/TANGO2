import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './EvalComparison.module.scss';

const cx = classNames.bind(style);

// 메트릭 값 표시 — perplexity 등 큰 수는 정수부, 0~100 스케일은 소수 2자리. (SP-5 Evaluate 와 동일)
const fmtMetric = (v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
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

  if (runs.length === 0) {
    return <div className={cx('empty')}>{t('evaluate.empty')}</div>;
  }

  return (
    <div className={cx('comparison')}>
      <div className={cx('table-wrap')}>
        <table className={cx('comparison-table')}>
          <thead>
            <tr>
              {showModel && <th>{t('evaluate.model.label')}</th>}
              <th>{t('evaluate.dataset.label')}</th>
              {metricKeys.map((k) => (
                <th key={k}>{k}</th>
              ))}
              <th>{t('evaluate.status.label')}</th>
              <th>{t('createdAt.label')}</th>
              {canDelete && <th className={cx('action-col')}>{t('evaluate.action.label')}</th>}
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                {showModel && (
                  <td className={cx('model-cell')}>{run.model_name || '-'}</td>
                )}
                <td>{run.dataset_name || '-'}</td>
                {metricKeys.map((k) => {
                  const v = run.metrics?.[k];
                  const isBest = best[k] === run.id && v !== undefined;
                  return (
                    <td key={k} className={cx('metric-cell', isBest && 'best')}>
                      {v !== undefined ? fmtMetric(v) : '-'}
                      {isBest && (
                        <span className={cx('best-badge')}>{t('evaluate.best.badge')}</span>
                      )}
                    </td>
                  );
                })}
                <td className={cx('run-status', run.status)}>
                  {t(`evaluate.status.${run.status || 'pending'}`)}
                </td>
                <td>{run.create_datetime || '-'}</td>
                {canDelete && (
                  <td className={cx('action-col')}>
                    <button
                      type="button"
                      className={cx('delete-btn')}
                      title={t('evaluate.action.delete')}
                      onClick={() => onDelete(run)}
                    >
                      {t('evaluate.action.delete')}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={cx('comparison-hint')}>{t('evaluate.comparison.hint')}</div>
    </div>
  );
};

export default EvalComparison;
