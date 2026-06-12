// Components
import { Button, ButtonV2, Radio } from '@tango/ui-react';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

import Table from '@src/components/molecules/Table';
import RecordsNav from '@src/components/pageContents/admin/AdminRecordContent/RecordsNav';
import { toast } from '@src/components/Toast';

// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import SimpleNav from '../SimpleNav';
import CommitListDetail from './CommitListDetail';

import classNames from 'classnames/bind';
import style from './CommitList.module.scss';

const cx = classNames.bind(style);

// ** [액션] 커밋 리스트 클릭 핸들러 **
const handleDetail = (row, match, history) => {
  history.push(
    `/user/workspace/${row.workspace_id}/model/${row.model_id}/commit-list/${row.id}`,
  );
};

const CommitList = memo(function CommitList({ navList, data, ...rest }) {
  const { t } = useTranslation();

  const history = useHistory();
  const { modelId } = data;

  const [commitList, setCommitList] = useState([{ list: [], model_name: '-' }]);

  // :id/model/:mId/commitList/:cid'
  const match = useRouteMatch();
  const { id: workspaceId, cId: commitId } = match.params;

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // get commit list
  const getCommitList = useCallback(async () => {
    const response = await callApi({
      url: `models/commit-models?model_id=${modelId}`,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      // commit_datetime 내림차순 (최신 위) + 가장 최근 항목에 (최신) 라벨
      const list = Array.isArray(result?.list) ? [...result.list] : [];
      list.sort((a, b) => {
        const da = a?.commit_datetime ?? '';
        const db = b?.commit_datetime ?? '';
        return db.localeCompare(da);
      });
      setCommitList({ ...result, list });
    } else {
      errorToastMessage(error, message);
    }
  }, [modelId]);

  const columns = [
    {
      name: t('commitName.label'),
      selector: 'name',
      cell: (row) => {
        const name = row?.name ?? '-';
        // 정렬된 list 의 첫 entry == 최신 commit. (최신) 라벨 표시.
        const isLatest =
          Array.isArray(commitList?.list) &&
          commitList.list.length > 0 &&
          commitList.list[0]?.id === row?.id;
        if (!isLatest) return name;
        return (
          <span>
            {name}
            <span
              style={{
                marginLeft: 6,
                padding: '1px 6px',
                fontSize: 10,
                background: '#4CAF50',
                color: '#fff',
                borderRadius: 3,
              }}
            >
              최신
            </span>
          </span>
        );
      },
    },
    {
      name: t('commitMessage.label'),
      selector: 'message',
      cell: ({ commit_message: message }) => {
        return message ?? '-';
      },
    },
    {
      name: t('writer.label'),
      selector: 'writer',
      cell: ({ create_user_name: user }) => {
        return user ?? '-';
      },
    },
    {
      name: t('commitDate.label'),
      selector: 'date',
      cell: ({ commit_datetime: datetime }) => {
        return datetime ?? '-';
      },
    },
  ];

  const ExpandedComponent = (row) => {
    return <CommitListDetail data={row.data} t={t} />;
  };

  useEffect(() => {
    getCommitList();
  }, [getCommitList]);

  return (
    <div id='finetuning-commit' className={cx('container')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        titleName={commitList.model_name}
      />
      <Table
        columns={columns}
        data={commitList.list}
        hideSearchBox={true}
        selectableRows={false}
        onRowClick={(row) => handleDetail(row, match, history)}
        // ExpandedComponent={ExpandedComponent}
      />
    </div>
  );
});

export default CommitList;
