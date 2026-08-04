import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import { getPromptCandidates } from '@src/apis/flightbase/synthesis';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisPromptListContent.module.scss';

const cx = classNames.bind(style);

const STATUS_LABEL_KEYS = {
  candidate: 'synthesis.prompt.status.candidate',
  adopted: 'synthesis.prompt.status.adopted',
  discarded: 'synthesis.prompt.status.discarded',
};

export default function UserSynthesisPromptListContent() {
  const { t } = useTranslation();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [data, setData] = useState({
    candidates: [],
    method: 'OPRO',
    mock: false,
  });

  const fetchCandidates = useCallback(async () => {
    const { result, status, message } = await getPromptCandidates(projectId);
    if (status === STATUS_SUCCESS) setData(result);
    else toast.error(message);
  }, [projectId]);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  const rows = data.candidates || [];

  return (
    <div className={cx('cont')}>
      <button
        className={cx('back-to-list')}
        onClick={() =>
          history.push(
            `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/overview`,
          )
        }
      >
        <img
          className={cx('back-btn-image')}
          src='/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='<'
        />
        <span className={cx('back-btn-label')}>
          {t('synthesis.overview.label')}
        </span>
      </button>
      <div className={cx('head')}>
        <h1 className={cx('title')}>{t('synthesis.promptList.title')}</h1>
        <ButtonV2
          type='outline'
          label={t('synthesis.action.optimizeCuration')}
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-optimize`,
            )
          }
        />
      </div>
      <p className={cx('desc')}>
        {t('synthesis.promptList.desc', { method: data.method })}{' '}
        {data.mock && <span className={cx('mock')}>[mock]</span>}
      </p>

      {rows.length === 0 ? (
        <div className={cx('empty')}>{t('synthesis.promptList.empty')}</div>
      ) : (
        <table className={cx('table')}>
          <thead>
            <tr>
              <th>iteration</th>
              <th>score</th>
              <th>prompt</th>
              <th>{t('status.label')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.iteration}</td>
                <td>{c.score}</td>
                <td className={cx('prompt-cell')}>{c.prompt}</td>
                <td>
                  <span className={cx('badge', c.status)}>
                    {STATUS_LABEL_KEYS[c.status]
                      ? t(STATUS_LABEL_KEYS[c.status])
                      : c.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
