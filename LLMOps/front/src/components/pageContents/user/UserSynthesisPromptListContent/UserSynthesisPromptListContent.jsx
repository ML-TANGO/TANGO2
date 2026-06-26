import React, { useCallback, useEffect, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';

import { getPromptCandidates } from '@src/apis/flightbase/synthesis';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './UserSynthesisPromptListContent.module.scss';

const cx = classNames.bind(style);

const STATUS_LABEL = { candidate: '후보', adopted: '채택', discarded: '폐기' };

export default function UserSynthesisPromptListContent() {
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, sid: projectId } = match.params;

  const [data, setData] = useState({ candidates: [], method: 'OPRO', mock: false });

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
        className={cx('back')}
        onClick={() =>
          history.push(
            `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/overview`,
          )
        }
      >
        ← 개요
      </button>
      <div className={cx('head')}>
        <h1 className={cx('title')}>프롬프트 후보 목록</h1>
        <ButtonV2
          type='outline'
          label='⚙ 최적화/큐레이션'
          onClick={() =>
            history.push(
              `/user/workspace/${workspaceId}/datasets/synthesis/${projectId}/prompt-optimize`,
            )
          }
        />
      </div>
      <p className={cx('desc')}>
        LLM1 이 생성한 모든 프롬프트 후보와 채택/폐기 이력입니다. (방식:{' '}
        {data.method}){' '}
        {data.mock && <span className={cx('mock')}>[mock]</span>}
      </p>

      {rows.length === 0 ? (
        <div className={cx('empty')}>
          후보가 없습니다. “최적화/큐레이션” 화면에서 생성하세요.
        </div>
      ) : (
        <table className={cx('table')}>
          <thead>
            <tr>
              <th>iteration</th>
              <th>score</th>
              <th>prompt</th>
              <th>상태</th>
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
                    {STATUS_LABEL[c.status] || c.status}
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
