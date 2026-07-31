import React from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { getMonitoringId } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PlaygroundNavigation.module.scss';

const cx = classNames.bind(style);

export default function PlaygroundNavigation({ isFetchingStatus }) {
  const history = useHistory();
  const { t } = useTranslation();

  const match = useRouteMatch();
  const { id: workspaceId, did: playgroundId } = match.params;

  const { status } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { init_deployment } = status;

  const handleBackGo = (workspaceId, history) => {
    history.push(`/user/workspace/${workspaceId}/llmplayground`);
  };

  const handleMonitoringGo = async (
    isFetchingStatus,
    workspaceId,
    playgroundId,
    history,
    t,
  ) => {
    if (isFetchingStatus)
      return toast.error(t('playground.deploy.monitor.error.message'));

    const { status, result, message } = await getMonitoringId(playgroundId);
    if (status === STATUS_SUCCESS) {
      const { playground_id, embedding_id, reranker_id } = result;

      if (playground_id) {
        history.push(
          `/user/workspace/${workspaceId}/llmplayground/${playground_id}/detail/${playgroundId}/playgroundmonitor`,
          {
            backPlaygroundId: playgroundId,
            playground_id,
            embedding_id,
            reranker_id,
          },
        );
      } else {
        toast.error(t('playground.header.deploy.message'));
      }
    } else {
      toast.error(message);
    }
  };

  return (
    <div className={cx('navigate-header-cont')}>
      <button
        className={cx('back-btn', 'button')}
        onClick={() => handleBackGo(workspaceId, history)}
        aria-label={'플레이 그라운드 메뉴로 이동'}
      >
        <img
          src={'/src/static/images/icon/00-ic-basic-arrow-02-left.svg'}
          alt=''
        />
        <span>{t('playground.label')}</span>
      </button>
      {init_deployment && (
        <button
          className={cx('monitor-btn', 'button')}
          onClick={() =>
            handleMonitoringGo(
              isFetchingStatus,
              workspaceId,
              playgroundId,
              history,
              t,
            )
          }
          alt='모니터링 페이지로 이동'
        >
          <span>{t('deployment.monitor')}</span>
          <img
            src={'/src/static/images/icon/00-ic-basic-arrow-02-left.svg'}
            alt=''
          />
        </button>
      )}
    </div>
  );
}
