import React from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

// CSS Module
import classNames from 'classnames/bind';
import style from './PlaygroundNavigation.module.scss';

const cx = classNames.bind(style);

export default function PlaygroundNavigation() {
  const history = useHistory();
  const { t } = useTranslation();

  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const handleBackGo = (workspaceId, history) => {
    history.push(`/user/workspace/${workspaceId}/llmplayground`);
  };

  return (
    <div className={cx('navigate-header-cont')}>
      <button
        className={cx('back-btn', 'button')}
        onClick={() => handleBackGo(workspaceId, history)}
        aria-label={'배포 메뉴로 이동'}
      >
        <img
          src={'/src/static/images/icon/00-ic-basic-arrow-02-left.svg'}
          alt=''
        />
        <span>{t('playground.label')}</span>
      </button>
    </div>
  );
}
