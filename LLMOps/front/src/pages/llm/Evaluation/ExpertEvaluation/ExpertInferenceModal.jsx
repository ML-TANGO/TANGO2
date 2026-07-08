import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getPlayground } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ExpertInferenceModal.module.scss';

const cx = classNames.bind(style);

// 전문가 평가 시작 전 "추론에 사용할 배포" 선택 모달.
//   워크스페이스의 running 배포(playground)를 나열 → 선택 시 그 배포 모델로 지연 단위 VLM
//   실추론(전문가가 여는 샘플만). 선택 안 함 → mock 출력으로 진행(graceful). running 없으면 mock 안내.
//   (배포↔프로젝트 모델 매칭은 사용자 선택 신뢰 — 리스트 API 가 비-dual 모델 id 를 안 실어줌.)
const ExpertInferenceModal = ({ workspaceId, onConfirm, onClose }) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=로딩, []=없음
  const [selected, setSelected] = useState(null); // playground id | null(mock)

  useEffect(() => {
    let active = true;
    (async () => {
      const res = await getPlayground(workspaceId);
      if (!active) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        setDeployments([]);
        return;
      }
      const raw = Array.isArray(res.result) ? res.result : [];
      const running = raw.filter((p) => p && p.status === 'running');
      setDeployments(running);
      // 실추론이 happy path — running 이 하나면 기본 선택, 여럿/없음이면 사용자 선택.
      if (running.length === 1) setSelected(running[0].id);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId]);

  const loading = deployments === null;

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
            {t('evaluation.expert.inferTitle')}
          </h2>
          <button type='button' className={cx('close-btn')} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={cx('modal-body')}>
          <p className={cx('desc')}>{t('evaluation.expert.inferDesc')}</p>

          {loading ? (
            <p className={cx('empty')}>{t('evaluation.project.loading')}</p>
          ) : (
            <div className={cx('deploy-list')}>
              {deployments.map((d) => (
                <button
                  key={d.id}
                  type='button'
                  className={cx('deploy-card', selected === d.id && 'on')}
                  onClick={() => setSelected(d.id)}
                >
                  <span className={cx('radio', selected === d.id && 'on')} />
                  <span className={cx('deploy-name')}>{d.name}</span>
                  <span className={cx('deploy-badge')}>running</span>
                </button>
              ))}
              <button
                type='button'
                className={cx('deploy-card', selected === null && 'on')}
                onClick={() => setSelected(null)}
              >
                <span className={cx('radio', selected === null && 'on')} />
                <span className={cx('deploy-name')}>
                  {t('evaluation.expert.inferNone')}
                </span>
              </button>
              {deployments.length === 0 && (
                <p className={cx('hint')}>
                  {t('evaluation.expert.inferNoRunning')}
                </p>
              )}
            </div>
          )}
        </div>

        <div className={cx('modal-foot')}>
          <button type='button' className={cx('cancel-btn')} onClick={onClose}>
            {t('cancel.label')}
          </button>
          <button
            type='button'
            className={cx('confirm-btn')}
            disabled={loading}
            onClick={() => onConfirm(selected)}
          >
            {t('evaluation.expert.inferStart')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExpertInferenceModal;
