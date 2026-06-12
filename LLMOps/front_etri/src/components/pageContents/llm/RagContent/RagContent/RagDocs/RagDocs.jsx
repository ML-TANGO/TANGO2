import { ButtonV2 } from '@tango/ui-react';

import { deleteRagDocuments, getRagDocuments } from '@src/apis/llm/rag';
import WarningIcon from '@src/static/images/icon/ic-warning-yellow.svg';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import Table from '@src/components/molecules/Table';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  convertByte,
  convertSizeToBytes,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

import useSSEDocs from './useSSEDocs';

import classNames from 'classnames/bind';
import style from './RagDocs.module.scss';

const cx = classNames.bind(style);

const statusRender = (status, t) => {
  switch (status) {
    case 'failed': // 업로드 실패
      return (
        <div className={cx(status)}>
          <img src={WarningIcon} alt='icon' />
          {t('uploadFail.label')}
        </div>
      );
    case 'pending': // 업로드 대기 중
      return t('uploadingPending.label');
    case 'uploading': // 업로드 중
      return (
        <div className={cx('uploading')}>
          <span>{t('uploading')}</span>
          <span>50 %</span>
        </div>
      );
    case 'done': // 사용 가능
      return t('currentAvailableCount');
    default:
      return '';
  }
};

function RagDocs({ navList, ...rest }) {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const { setting, info, instance } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );
  const { id: workspaceId, rid: ragId } = match.params;

  const {
    reranker_model: rerankerModel,
    doc_list: docList,
    embedding_model: embeddingModel,
    chunk_len: chunkLen,
  } = setting;
  const [ragSetting, setRagSetting] = useState(null);
  const [tableData, setTableData] = useState([]);
  const [selectedRows, setSelectedRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const isLoading = useRef(false);

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // ** 문서 삭제
  const onDelete = async () => {
    setLoading(true);
    const selectedRowId = selectedRows.map(({ id }) => id);
    const res = await deleteRagDocuments({ ragId, list: selectedRowId });

    const { error, message, status } = res;

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      setSelectedRows([]);
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  // ** 체크박스 선택
  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  const bottomButtonList = (
    <>
      <ButtonV2
        colorType='red'
        onClick={onDelete}
        disabled={selectedRows.length === 0}
        loading={loading}
      >
        {t('delete.label')}
      </ButtonV2>
    </>
  );

  const columns = [
    {
      name: t('name.label'),
      selector: 'name',
      minWidth: '600px',
      cell: ({ name }) => {
        return name ?? '-';
      },
    },
    {
      name: t('status.label'),
      selector: 'status',
      cell: ({ status }) => {
        return (
          <div className={cx('upload-status')}>{statusRender(status, t)}</div>
        );
      },
    },
    {
      name: t('size.label'),
      selector: 'size',
      // maxWidth: '150px',
      cell: ({ size }) => {
        return convertByte(size ?? '-');
      },
    },
    {
      name: t('llm.rag.Craetor.label'),
      selector: 'creator',
      cell: ({ owner }) => {
        return owner ?? '-';
      },
    },
    {
      name: t('uploadedAt.label'),
      selector: 'uploadDate',
      cell: ({ create_datetime: createDatetime }) => {
        return createDatetime ?? '-';
      },
    },
  ];

  useSSEDocs(ragId, userName, setTableData);

  return (
    <div className={cx('container')}>
      <Table
        columns={columns}
        data={tableData}
        hideSearchBox={true}
        onSelect={onSelect}
        bottomButtonList={tableData?.length > 0 && bottomButtonList}
      />
    </div>
  );
}

export default RagDocs;
