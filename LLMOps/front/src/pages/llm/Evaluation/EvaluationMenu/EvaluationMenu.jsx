import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { startPath } from '@src/store/modules/breadCrumb';

import classNames from 'classnames/bind';
import style from './EvaluationMenu.module.scss';

const cx = classNames.bind(style);

// 평가(Evaluation) 허브 — 3 모드 picker. P1c=벤치마크 active.
//   LLM-as-a-Judge=P2 / 전문가 평가=P3 (준비중). ETRI IA(단일 평가 메뉴→모드 분기) 채택.
const MODES = [
  {
    id: 'benchmark', icon: '📊', ready: true,
    titleKey: 'evaluation.mode.benchmark.title',
    descKey: 'evaluation.mode.benchmark.desc',
  },
  {
    id: 'judge', icon: '⚖️', ready: false,
    titleKey: 'evaluation.mode.judge.title',
    descKey: 'evaluation.mode.judge.desc',
  },
  {
    id: 'expert', icon: '👤', ready: false,
    titleKey: 'evaluation.mode.expert.title',
    descKey: 'evaluation.mode.expert.desc',
  },
];

const EvaluationMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
  }, [dispatch]);

  const open = (mode) => {
    if (!mode.ready) return;
    history.push(`/user/workspace/${workspaceId}/evaluation/${mode.id}`);
  };

  return (
    <div className={cx('evaluation-hub')}>
      <h1 className={cx('title')}>{t('Evaluation')}</h1>
      <p className={cx('subtitle')}>{t('evaluation.hub.subtitle')}</p>
      <div className={cx('mode-grid')}>
        {MODES.map((m) => (
          <button
            key={m.id}
            type='button'
            className={cx('mode-card', !m.ready && 'disabled')}
            onClick={() => open(m)}
            disabled={!m.ready}
          >
            <span className={cx('mode-icon')}>{m.icon}</span>
            <span className={cx('mode-title')}>{t(m.titleKey)}</span>
            <span className={cx('mode-desc')}>{t(m.descKey)}</span>
            {!m.ready && (
              <span className={cx('mode-soon')}>{t('evaluation.comingSoon')}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};

export default EvaluationMenu;
