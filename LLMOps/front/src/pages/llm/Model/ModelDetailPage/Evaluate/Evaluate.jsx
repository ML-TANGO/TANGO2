import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { callApi, STATUS_SUCCESS } from '@src/network';
import { getEvaluateResults } from '@src/apis/llm/model';

import SimpleNav from '../SimpleNav';

import classNames from 'classnames/bind';
import style from './Evaluate.module.scss';

const cx = classNames.bind(style);

// 메트릭 값 표시 — perplexity 등 큰 수는 정수부, 0~100 스케일은 소수 2자리.
const fmtMetric = (v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

/**
 * 모델 상세 '평가' 탭 (v0.4 3.8 / QA 항목 3) — 이력 전용 읽기 뷰.
 * 평가 실행은 '평가(Evaluation)' 허브로 이전(§14.12 ③). 이 탭은 해당 모델의 평가 이력
 * (공용 eval_result: 자체 메트릭 런 + 벤치마크 런)만 비교표로 보여주고, 상단 버튼으로
 * 평가 페이지로 이동한다.
 */
const Evaluate = memo(function Evaluate({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const history = useHistory();
  const { modelId, workspaceId } = data;

  const [titleName, setTitleName] = useState('');
  const [comparison, setComparison] = useState(null); // { metric_keys, best, runs }

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // 모델명 (SimpleNav 타이틀용)
  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      if (alive && res.status === STATUS_SUCCESS)
        setTitleName(res.result?.name ?? '');
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 이 모델의 평가 이력 비교표 (마운트 시)
  const fetchComparison = useCallback(async () => {
    const res = await getEvaluateResults(modelId);
    if (res.status === STATUS_SUCCESS) setComparison(res.result);
  }, [modelId]);

  useEffect(() => {
    fetchComparison();
  }, [fetchComparison]);

  const goToEvaluation = useCallback(() => {
    if (workspaceId) history.push(`/user/workspace/${workspaceId}/evaluation`);
  }, [history, workspaceId]);

  const metricKeys = comparison?.metric_keys ?? [];
  const best = comparison?.best ?? {};
  const runs = comparison?.runs ?? [];

  return (
    <div id='evaluate-tab' className={cx('evaluate-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        titleName={titleName}
        topButtonList={
          <ButtonV2
            colorType='blue'
            label={t('evaluate.relocated.cta')}
            onClick={goToEvaluation}
          />
        }
      />

      <div className={cx('container')}>
        <div className={cx('intro')}>
          <div className={cx('intro-head')}>
            <div>
              <div className={cx('intro-title')}>{t('evaluate.label')}</div>
            </div>
          </div>
        </div>

        {runs.length > 0 ? (
          <div className={cx('comparison')}>
            <div className={cx('comparison-title')}>
              {t('evaluate.comparison.label')}
            </div>
            <div className={cx('table-wrap')}>
              <table className={cx('comparison-table')}>
                <thead>
                  <tr>
                    <th>{t('evaluate.dataset.label')}</th>
                    {metricKeys.map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                    <th>{t('evaluate.status.label')}</th>
                    <th>{t('createdAt.label')}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id}>
                      <td>{run.dataset_name || '-'}</td>
                      {metricKeys.map((k) => {
                        const v = run.metrics?.[k];
                        const isBest = best[k] === run.id && v !== undefined;
                        return (
                          <td
                            key={k}
                            className={cx('metric-cell', isBest && 'best')}
                          >
                            {v !== undefined ? fmtMetric(v) : '-'}
                            {isBest && (
                              <span className={cx('best-badge')}>
                                {t('evaluate.best.badge')}
                              </span>
                            )}
                          </td>
                        );
                      })}
                      <td className={cx('run-status', run.status)}>
                        {t(`evaluate.status.${run.status || 'pending'}`)}
                      </td>
                      <td>{run.create_datetime || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={cx('comparison-hint')}>
              {t('evaluate.comparison.hint')}
            </div>
          </div>
        ) : (
          <div className={cx('empty')}>
            <div className={cx('empty-text')}>{t('evaluate.empty')}</div>
          </div>
        )}
      </div>
    </div>
  );
});

export default Evaluate;
