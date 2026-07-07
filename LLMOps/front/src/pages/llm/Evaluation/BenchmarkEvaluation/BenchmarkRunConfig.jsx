import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { METRICS } from './benchmarkMetrics';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// 벤치마크 실행 설정(프로젝트 상속) — 모델·데이터셋은 프로젝트에서 잠금이라 여기선 17메트릭만 선택.
// onRun(metric_set) 로 상위(ProjectDetail)가 runBenchmark({ project_id, metric_set }) 호출.
// 구 standalone BenchmarkEvaluation 의 셋업 UI(ModelSelector+데이터셋 피커)는 제거하고 이 블록만 재사용.
const BenchmarkRunConfig = ({ running, onRun }) => {
  const { t } = useTranslation();
  const [selMetrics, setSelMetrics] = useState([]);

  const toggle = (id) =>
    setSelMetrics((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const canRun = selMetrics.length > 0 && !running;

  return (
    <div className={cx('benchmark')}>
      <section className={cx('section')}>
        <div className={cx('ds-section-header')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.selectMetrics')} (17)
          </h3>
          {selMetrics.length > 0 && (
            <span className={cx('ds-count-badge')}>{selMetrics.length}</span>
          )}
        </div>
        <div className={cx('option-grid')}>
          {METRICS.map((m) => (
            <div
              key={m.id}
              className={cx(
                'option-card',
                selMetrics.includes(m.id) && 'selected',
              )}
              onClick={() => toggle(m.id)}
            >
              <div className={cx('option-name')}>{m.label}</div>
              <div className={cx('option-desc')}>{m.desc}</div>
            </div>
          ))}
        </div>
      </section>

      <div className={cx('run-row')}>
        <button
          type='button'
          className={cx('run-btn', !canRun && 'disabled')}
          disabled={!canRun}
          onClick={() => canRun && onRun(selMetrics)}
        >
          {running ? t('evaluation.running') : t('evaluation.runBenchmark')}
        </button>
      </div>
    </div>
  );
};

export default BenchmarkRunConfig;
