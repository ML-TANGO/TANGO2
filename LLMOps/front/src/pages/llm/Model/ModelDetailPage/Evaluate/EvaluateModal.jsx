import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { getDatasetList } from '@src/apis/flightbase/trainings';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './EvaluateModal.module.scss';

const cx = classNames.bind(style);

// SP-5 자체 메트릭(SaaS judge 비의존). prompt+reference → BLEU/ROUGE, text → perplexity.
const METRIC_OPTIONS = [
  { value: 'bleu', titleKey: 'evaluate.metric.bleu', descKey: 'evaluate.metric.bleu.desc' },
  { value: 'rouge', titleKey: 'evaluate.metric.rouge', descKey: 'evaluate.metric.rouge.desc' },
  { value: 'perplexity', titleKey: 'evaluate.metric.perplexity', descKey: 'evaluate.metric.perplexity.desc' },
];

const DEFAULT_METRICS = ['bleu', 'rouge', 'perplexity'];

/**
 * 평가 실행 모달 (자체 오버레이 — Redux modal registry 비의존).
 * 평가 데이터셋 선택 + 메트릭(BLEU/ROUGE/perplexity) 토글 + 샘플 수 → evaluate launch.
 */
const EvaluateModal = ({ open, onClose, onConfirm, submitting, workspaceId }) => {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState('');
  const [metrics, setMetrics] = useState(DEFAULT_METRICS);
  const [maxSamples, setMaxSamples] = useState(50);

  // 모달 열릴 때 폼 리셋 + 워크스페이스 데이터셋 목록 로드.
  useEffect(() => {
    if (!open) return undefined;
    setDatasetId('');
    setMetrics(DEFAULT_METRICS);
    setMaxSamples(50);
    let alive = true;
    (async () => {
      const res = await getDatasetList(workspaceId);
      if (alive && res.status === STATUS_SUCCESS) setDatasets(res.result ?? []);
    })();
    return () => {
      alive = false;
    };
  }, [open, workspaceId]);

  if (!open) return null;

  const toggleMetric = (value) => {
    setMetrics((prev) =>
      prev.includes(value) ? prev.filter((m) => m !== value) : [...prev, value],
    );
  };

  const canSubmit = !!datasetId && metrics.length > 0 && !submitting;

  const handleConfirm = () => {
    if (!canSubmit) return;
    const ms = Math.max(1, Math.min(1000, parseInt(maxSamples, 10) || 50));
    onConfirm({
      dataset_id: Number(datasetId),
      metric_set: metrics,
      max_samples: ms,
    });
  };

  return (
    <div className={cx('overlay')} onClick={submitting ? undefined : onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('title')}>{t('evaluate.modal.title')}</div>
        <div className={cx('subtitle')}>{t('evaluate.modal.desc')}</div>

        <div className={cx('section-label')}>{t('evaluate.dataset.label')}</div>
        <select
          className={cx('dataset-select')}
          value={datasetId}
          onChange={(e) => setDatasetId(e.target.value)}
          disabled={submitting}
        >
          <option value=''>{t('evaluate.dataset.placeholder')}</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.dataset_name || d.name}
            </option>
          ))}
        </select>
        {datasets.length === 0 && (
          <div className={cx('dataset-empty')}>{t('evaluate.dataset.empty')}</div>
        )}

        <div className={cx('section-label')}>{t('evaluate.metric.label')}</div>
        <div className={cx('options')}>
          {METRIC_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={cx('option', metrics.includes(opt.value) && 'selected')}
            >
              <input
                type='checkbox'
                checked={metrics.includes(opt.value)}
                onChange={() => toggleMetric(opt.value)}
                disabled={submitting}
              />
              <div className={cx('option-text')}>
                <div className={cx('option-title')}>{t(opt.titleKey)}</div>
                <div className={cx('option-desc')}>{t(opt.descKey)}</div>
              </div>
            </label>
          ))}
        </div>

        <div className={cx('section-label')}>{t('evaluate.maxSamples.label')}</div>
        <input
          className={cx('samples-input')}
          type='number'
          min={1}
          max={1000}
          value={maxSamples}
          onChange={(e) => setMaxSamples(e.target.value)}
          disabled={submitting}
        />
        <div className={cx('samples-hint')}>{t('evaluate.maxSamples.hint')}</div>

        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            label={t('cancel.label')}
            onClick={onClose}
            disabled={submitting}
          />
          <ButtonV2
            colorType='blue'
            label={t('evaluate.start.label')}
            onClick={handleConfirm}
            disabled={!canSubmit}
          />
        </div>
      </div>
    </div>
  );
};

export default EvaluateModal;
