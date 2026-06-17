import { ButtonV2, Loading } from '@tango/ui-react';

import { getRagSystemLog, getRagSystemLogDownload } from '@src/apis/llm/rag';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { copyToClipboard, errorToastMessage } from '@src/utils';

import Tab from '../EditWorkspaceResource/Tab';
import NewStyleModalFrame from '../NewStyleModalFrame';
import useSSELog from './useSSELog';

import classNames from 'classnames/bind';
import style from './RagSystemLogModal.module.scss';

const cx = classNames.bind(style);

const noSelectedDataMessage = {
  first: 'datasetSelect.message',
  second: 'trainingDataSelect.message',
};

const title = {
  first: 'dataset.label',
  second: 'trainingData.label',
};

const initialModelData = {
  keyword: '',
  selectedModel: null,
  selectedOption: {
    label: 'total.label',
    value: 'total',
  },
};

const RagSystemLogModal = ({ data, type }) => {
  const { workspaceId, refresh, ragId, git, ragType, modelName } = data;

  const dispatch = useDispatch();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const [log, setLog] = useState('');
  const [footerMessage, setFooterMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const [datasetData, setDatasetData] = useState(initialModelData);
  const [trainingData, setTrainingData] = useState(initialModelData);
  // ** 탭 **
  const [tabValue, setTabValue] = useState(0);
  const [logData, setLogData] = useState({
    name: '-',
    embedding: null,
    reranker: null,
  });

  const { t } = useTranslation();

  // POST Submit TrainingPage
  const postDatasetFiles = async () => {
    const { id } = datasetData.selectedModel; // dataset id
    const { name } = trainingData.selectedModel; // path

    const response = await callApi({
      url: `models/add-dataset`,
      method: 'post',
      body: {
        dataset_id: id,
        training_data_path: name,
        model_id: ragId,
      },
    });
    const { status, result, message, error } = response;

    // null, ''랭스, 그이상

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('FINETUNING_DATA_UPLOAD'));
      refresh();
    } else {
      errorToastMessage(error, message);
    }
  };

  const onClickDownload = async () => {
    const { data, status } = await getRagSystemLogDownload();
    if (status === 200) {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[RAG]No.${ragId}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      errorToastMessage();
    }
  };

  useSSELog(ragId, userName, setLogData, ragType);

  return (
    <NewStyleModalFrame
      title={t('systemLog.label')}
      type={type}
      submit={{
        text: t('confirm.label'),
        func: () => {
          dispatch(closeModal('RAG_SYSTEM_LOG'));
        },
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('container')}>
        <Tab
          tabValue={tabValue}
          handleTab={setTabValue}
          leftText={'llm.rag.embeddingModel.label'}
          rightText={'llm.rag.reRanker.label'}
        />
        <div className={cx('title')}>
          <div className={cx('name')}>{logData.name}</div>
          <ButtonV2
            type='solid'
            size='l'
            colorType='skyblue'
            label={`CSV ${t('download.label')}`}
            // disabled={disabled}
            onClick={onClickDownload}
            // style={{ width: '100%',  }}
          />
        </div>
        <div className={cx('content')}>
          {loading && (
            <div className={cx('no-data')}>
              <Loading />
            </div>
          )}

          {!loading &&
            (tabValue === 0 ? (
              logData.embedding ? (
                logData.embedding
              ) : (
                <div className={cx('no-data')}>{t('noData.message')}</div>
              )
            ) : logData.reranker ? (
              logData.reranker
            ) : (
              <div className={cx('no-data')}>{t('noData.message')}</div>
            ))}
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default RagSystemLogModal;
