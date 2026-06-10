import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useParams } from 'react-router-dom';

import CardList from '@src/components/molecules/CardTemplate/CardList';
import CreateCard from '@src/components/molecules/CardTemplate/CreateCard';

import {
  analysisGet,
  deleteAnalyzer,
  deleteAnalyzerBookmark,
  postAnalyzerBookmark,
} from '@src/apis/flightbase/dataset/analysis';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import AnalysisCard from './AnalysisCard';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserDatasetAnalysisContent.module.scss';

const cx = classNames.bind(style);

// * get
const getAnalysisList = async (setAnalysisList, wid) => {
  const response = await analysisGet(wid);

  const { result, status } = response;

  if (status === STATUS_SUCCESS) {
    const list = result
      .map(({ description, ...rest }) => ({
        ...rest,
        desc: description,
      }))
      .sort((a, b) => b.bookmark - a.bookmark);

    setAnalysisList(list);
  }
};

// * 삭제
const analysisDelete = async (id, wid, setAnalysisList) => {
  const response = await deleteAnalyzer({ id });

  const { status, error, message } = response;

  if (status === STATUS_SUCCESS) {
    getAnalysisList(setAnalysisList, wid);
    defaultSuccessToastMessage('delete');
  } else {
    errorToastMessage(error, message);
  }
};

const UserDatasetAnalysisContent = () => {
  const { t } = useTranslation();
  const { id: wid } = useParams();

  const [analysisList, setAnalysisList] = useState([]);
  const dispatch = useDispatch();

  // * bookmark
  const handleBookMark = async (e, analyzer_id, isBookMark) => {
    e.stopPropagation();
    if (!isBookMark) {
      await postAnalyzerBookmark({ analyzer_id });
    } else {
      await deleteAnalyzerBookmark({ analyzer_id });
    }
    getAnalysisList(setAnalysisList, wid);
  };

  // * 생성 모달
  const handleModal = () => {
    dispatch(
      openModal({
        modalType: 'ADD_DATASET_ANALYSIS',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              getAnalysisList(setAnalysisList, wid);
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspace_id: wid,
          modalType: 'ADD_DATASET_ANALYSIS',
        },
      }),
    );
  };

  useEffect(() => {
    getAnalysisList(setAnalysisList, wid);
  }, [wid]);

  useEffect(() => {
    loadModalComponent('ADD_DATASET_ANALYSIS');
  }, []);

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>{`${t('data.label')} ${t(
        'analyze.label',
      )}`}</div>
      <CardList>
        <CreateCard
          label={t('analysisCreate.label')}
          handleCreateCard={handleModal}
          minWidth={'302px'}
          height={'362px'}
        />
        {analysisList.map(
          ({ owner, name, desc, instance, id, access, bookmark }) => {
            const {
              cpu_allocate: cpu,
              gpu_allocate: gpu,
              ram_allocate: ram,
              instance_allocate: instanceAllocate,
            } = instance;

            return (
              <AnalysisCard
                key={id}
                id={id}
                owner={owner}
                name={name}
                desc={desc}
                gpu={gpu}
                cpu={cpu}
                ram={ram}
                instanceAllocate={instanceAllocate}
                instanceName={instance?.instance_name}
                access={access}
                isBookMark={bookmark ? true : false}
                handleBookMark={handleBookMark}
                deleteAnalysis={(id) =>
                  analysisDelete(id, wid, setAnalysisList)
                }
                fetchProcessList={() => getAnalysisList(setAnalysisList, wid)}
              />
            );
          },
        )}
      </CardList>
    </div>
  );
};

export default UserDatasetAnalysisContent;
