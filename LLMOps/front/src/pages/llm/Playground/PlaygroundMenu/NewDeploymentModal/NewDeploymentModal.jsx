import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './NewDeploymentModal.module.scss';

const cx = classNames.bind(style);

// 배포(D6 v3) 통합 생성 진입점 — 타겟 선택 후 해당 플로우로 라우팅.
//   현재클러스터 = Playground 생성(start)으로 직결.
//   온디바이스/standalone = 양자화 GGUF 패키지 선행 필요(SP-4) → 모델 양자화 플로우로 안내.
//   (풀 인-탭 온디바이스 생성[모델→lineage job→deployEdgeWorker]은 후속 enhancement.)
const TARGETS = [
  { id: 'cluster', label: 'deploymentTarget.cluster.label', desc: 'deploymentTarget.cluster.desc' },
  { id: 'edge', label: 'deploymentTarget.edge.label', desc: 'deploymentTarget.edge.desc' },
  { id: 'standalone', label: 'deploymentTarget.standalone.label', desc: 'deploymentTarget.standalone.desc' },
];

const NewDeploymentModal = ({ open, onClose, onSelectCluster }) => {
  const { t } = useTranslation();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [selected, setSelected] = useState(null);

  if (!open) return null;

  const handlePick = (id) => {
    if (id === 'cluster') {
      onClose();
      onSelectCluster();
      return;
    }
    setSelected(id); // edge / standalone → 선행(양자화) 안내
  };

  const goToModel = () => {
    onClose();
    history.push(`/user/workspace/${workspaceId}/model`);
  };

  const needsQuantize = selected === 'edge' || selected === 'standalone';

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('title')}>{t('deployment.create.title')}</div>

        <div className={cx('target-grid')}>
          {TARGETS.map((tg) => (
            <button
              key={tg.id}
              type='button'
              className={cx('target-card', selected === tg.id && 'selected')}
              onClick={() => handlePick(tg.id)}
            >
              <span className={cx('target-label')}>{t(tg.label)}</span>
              <span className={cx('target-desc')}>{t(tg.desc)}</span>
            </button>
          ))}
        </div>

        {needsQuantize && (
          <div className={cx('notice')}>
            <p>{t('deployment.requiresQuantize')}</p>
            <ButtonV2
              colorType='blue'
              label={t('goToModel.label')}
              onClick={goToModel}
            />
          </div>
        )}

        <div className={cx('actions')}>
          <ButtonV2 type='outline' label={t('cancel.label')} onClick={onClose} />
        </div>
      </div>
    </div>
  );
};

export default NewDeploymentModal;
