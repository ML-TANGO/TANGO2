import { getPromptList } from '@src/apis/llm/prompt';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import Table from '@src/components/molecules/Table';

import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './PromptCommitList.module.scss';

const cx = classNames.bind(style);

const getPromptDataList = async (promptId, setPromptList, setIsFetching) => {
  setIsFetching(true);
  const { result, message, status } = await getPromptList(promptId);
  if (status === STATUS_SUCCESS) {
    setPromptList(result);
  } else {
    toast.error(message);
  }
  setIsFetching(false);
};

// ** [액션] 커밋 리스트 클릭 핸들러 **
const handleDetail = (row, match, history) => {
  const currentUrl = match.url;
  const splitUrl = currentUrl.split('/');
  splitUrl.pop();
  const joinUrl = splitUrl.join('/');
  history.push(
    `${joinUrl}/detail/${row.commit_id}-${row.message}/promptcommit`,
  );
};

export default function PromptCommitList() {
  const { t } = useTranslation();
  const history = useHistory();

  const match = useRouteMatch();
  const { did: promptId } = match.params;

  // ** [데이터] 테이블 데이터 **
  const [promptList, setPromptList] = useState([]);
  const [isFetching, setIsFetching] = useState(false);
  const column = [
    {
      name: <span className={cx('header')}>{t('commitName.label')}</span>,
      selector: 'name',
      minWidth: '120px',
    },
    {
      name: <span className={cx('header')}>{t('commitMessage.label')}</span>,
      selector: 'message',
      grow: 840,
      cell: ({ message }) => {
        return (
          <div
            style={{
              whiteSpace: 'nowrap',
            }}
          >
            {message}
          </div>
        );
      },
    },
    {
      name: <span className={cx('header')}>{t('writer.label')}</span>,
      selector: 'user',
      grow: 128,
      cell: ({ user }) => {
        return user;
      },
      center: true,
    },
    {
      name: <span className={cx('header')}>{t('commitDate.label')}</span>,
      selector: 'datetime',
      cell: ({ datetime }) => {
        return datetime;
      },
      minWidth: '168px',
      center: true,
      compact: true,
    },
  ];

  // ! [사이드 이펙트] 초반 데이터 렌더 **
  useEffect(() => {
    getPromptDataList(promptId, setPromptList, setIsFetching);
  }, [promptId]);

  return (
    <Table
      columns={column}
      data={promptList}
      hideSearchBox={true}
      selectableRows={false}
      onRowClick={(row) => handleDetail(row, match, history)}
      loading={isFetching}
    />
  );
}
