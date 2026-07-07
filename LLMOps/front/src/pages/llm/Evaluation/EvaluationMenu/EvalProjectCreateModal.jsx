import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import { createEvalProject, getEvalDatasets } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalProjectCreateModal.module.scss';

const cx = classNames.bind(style);

const MAX_DATASETS = 10; // llm_evaluation dataset_ids max_length=10 (초과 시 BE 422)

// 평가 유형 3종 — 라벨/설명은 기존 evaluation.mode.* 재사용(중복 키 회피).
const TYPES = [
  {
    id: 'benchmark',
    icon: '📊',
    titleKey: 'evaluation.mode.benchmark.title',
    descKey: 'evaluation.mode.benchmark.desc',
  },
  {
    id: 'judge',
    icon: '⚖️',
    titleKey: 'evaluation.mode.judge.title',
    descKey: 'evaluation.mode.judge.desc',
  },
  {
    id: 'expert',
    icon: '👤',
    titleKey: 'evaluation.mode.expert.title',
    descKey: 'evaluation.mode.expert.desc',
  },
];

// 새 평가 프로젝트 생성 모달(ETRI New Evaluation 흐름 일반화, 설계 §6).
//   순서: 유형 → 모델(ModelSelector) → 데이터셋(멀티, cap 10) → 이름 → 생성(대기).
//   생성 성공 시 onCreated(get_project) 로 부모가 상세로 이동. model/dataset 은 생성 후 불변(P3 강제).
const EvalProjectCreateModal = ({ workspaceId, onClose, onCreated }) => {
  const { t } = useTranslation();

  const [evalType, setEvalType] = useState('benchmark');
  const [modelId, setModelId] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [selDatasets, setSelDatasets] = useState([]);
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    (async () => {
      const res = await getEvalDatasets(workspaceId);
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result)
          ? res.result
          : (res.result?.list ?? []);
        setDatasets(
          raw
            .map((d) => ({
              id: d.id ?? d.dataset_id,
              name: d.name ?? d.dataset_name,
              format: d.format ?? d.data_format ?? null,
            }))
            .filter((d) => d.id != null),
        );
      } else {
        errorToastMessage(res.error, res.message);
      }
    })();
  }, [workspaceId]);

  // 데이터셋은 BE cap(10) 클라이언트단 강제 — 초과 추가 시 토스트, 422 round-trip 회피.
  const toggleDataset = (id) => {
    if (selDatasets.includes(id)) {
      setSelDatasets(selDatasets.filter((x) => x !== id));
      return;
    }
    if (selDatasets.length >= MAX_DATASETS) {
      errorToastMessage(
        null,
        t('evaluation.datasetCap', { max: MAX_DATASETS }),
      );
      return;
    }
    setSelDatasets([...selDatasets, id]);
  };

  const filteredDatasets = useMemo(() => {
    const kw = datasetKeyword.trim().toLowerCase();
    if (!kw) return datasets;
    return datasets.filter((d) => (d.name || '').toLowerCase().includes(kw));
  }, [datasets, datasetKeyword]);

  const canCreate =
    !!name.trim() &&
    !!modelId &&
    selDatasets.length > 0 &&
    selDatasets.length <= MAX_DATASETS &&
    !creating;

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    // workspace_id 는 BE 가 model_id 로 도출(설계 계약 — 바디 미포함).
    const res = await createEvalProject({
      name: name.trim(),
      model_id: Number(modelId),
      dataset_ids: selDatasets,
      eval_type: evalType,
    });
    setCreating(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    onCreated?.(res.result);
  };

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div
        className={cx('modal')}
        onClick={(e) => e.stopPropagation()}
        role='dialog'
        aria-modal='true'
      >
        <div className={cx('modal-head')}>
          <h2 className={cx('modal-title')}>
            {t('evaluation.project.createTitle')}
          </h2>
          <button type='button' className={cx('close-btn')} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={cx('modal-body')}>
          <section className={cx('section')}>
            <h3 className={cx('section-title')}>
              {t('evaluation.project.selectType')}
            </h3>
            <div className={cx('type-grid')}>
              {TYPES.map((ty) => (
                <button
                  key={ty.id}
                  type='button'
                  className={cx('type-card', evalType === ty.id && 'selected')}
                  onClick={() => setEvalType(ty.id)}
                >
                  <span className={cx('type-icon')}>{ty.icon}</span>
                  <span className={cx('type-name')}>{t(ty.titleKey)}</span>
                  <span className={cx('type-desc')}>{t(ty.descKey)}</span>
                </button>
              ))}
            </div>
          </section>

          <section className={cx('section')}>
            <h3 className={cx('section-title')}>
              {t('evaluation.selectModel')}
            </h3>
            <ModelSelector
              wid={workspaceId}
              selected={modelId}
              onSelect={(id) => setModelId(id)}
            />
          </section>

          <section className={cx('section')}>
            <div className={cx('ds-section-header')}>
              <h3 className={cx('section-title')}>
                {t('evaluation.selectDatasets')}
              </h3>
              <span className={cx('ds-count-badge')}>{datasets.length}</span>
              <div className={cx('ds-spacer')} />
              {selDatasets.length > 0 && (
                <span className={cx('ds-selected-label')}>
                  <strong>{selDatasets.length}</strong> / {MAX_DATASETS}
                </span>
              )}
            </div>
            {datasets.length > 0 && (
              <div className={cx('ds-search-wrap')}>
                <input
                  className={cx('ds-search-input')}
                  placeholder={t('evaluation.searchDataset')}
                  value={datasetKeyword}
                  onChange={(e) => setDatasetKeyword(e.target.value)}
                />
                {datasetKeyword && (
                  <button
                    type='button'
                    className={cx('ds-search-clear')}
                    onClick={() => setDatasetKeyword('')}
                  >
                    ✕
                  </button>
                )}
              </div>
            )}
            {datasets.length === 0 ? (
              <p className={cx('empty')}>{t('evaluation.noDatasets')}</p>
            ) : filteredDatasets.length === 0 ? (
              <div className={cx('ds-empty')}>
                {t('evaluation.noSearchResult')}
              </div>
            ) : (
              <div className={cx('ds-list')}>
                {filteredDatasets.map((d) => {
                  const isSel = selDatasets.includes(d.id);
                  return (
                    <div
                      key={d.id}
                      className={cx('ds-card', isSel && 'ds-card--on')}
                      onClick={() => toggleDataset(d.id)}
                    >
                      <div className={cx('ds-check', isSel && 'ds-check--on')}>
                        {isSel && '✓'}
                      </div>
                      <div className={cx('ds-card-body')}>
                        <div className={cx('ds-card-name-row')}>
                          <span className={cx('ds-card-name')}>{d.name}</span>
                          {d.format && (
                            <span className={cx('ds-format-badge')}>
                              {d.format}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className={cx('section')}>
            <h3 className={cx('section-title')}>
              {t('evaluation.project.name')}
            </h3>
            <input
              className={cx('name-input')}
              type='text'
              placeholder={t('evaluation.project.namePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
            />
          </section>
        </div>

        <div className={cx('modal-foot')}>
          <button type='button' className={cx('cancel-btn')} onClick={onClose}>
            {t('cancel.label')}
          </button>
          <button
            type='button'
            className={cx('create-btn', !canCreate && 'disabled')}
            disabled={!canCreate}
            onClick={handleCreate}
          >
            {creating
              ? t('evaluation.project.creating')
              : t('evaluation.project.create')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EvalProjectCreateModal;
