import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';

import CardList from '@src/components/molecules/CardTemplate/CardList';
import CreateCard from '@src/components/molecules/CardTemplate/CreateCard';

import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import ProcessCard from './ProcessCard';

import classNames from 'classnames/bind';
import style from './UserDatasetPreprocessContent.module.scss';

const cx = classNames.bind(style);

const UserDatasetPreprocessContent = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { id: wid } = useParams();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));
  const { userName: loginUser } = auth;

  const [processList, setProcessList] = useState([]);

  const fetchProcessList = async () => {
    const response = await callApi({
      url: `preprocessing?workspace_id=${wid}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { list } = result;
      const processList = list.map(
        ({
          id,
          access,
          owner_name,
          name,
          description,
          instance_name,
          gpu_allocate,
          cpu_allocate,
          ram_allocate,
          instance_allocate,
          status,
          type,
          update_datetime,
          bookmark,
          private_user_list,
        }) => ({
          id,
          owner: owner_name,
          name,
          instanceAllocate: instance_allocate,
          instance: instance_name,
          desc: description,
          cpu: cpu_allocate,
          gpu: gpu_allocate,
          ram: ram_allocate,
          access,
          jobStatus: status.job,
          type,
          time: update_datetime,
          isBookmark: bookmark ? true : false,
          userList: private_user_list,
        }),
      );

      setProcessList(processList);
    }
  };

  const deleteProcess = async (id) => {
    const response = await callApi({
      url: `preprocessing`,
      method: 'delete',
      body: {
        id_list: [id],
      },
    });

    const { status } = response;

    if (status === STATUS_SUCCESS) {
      fetchProcessList();
    }
  };

  const bookmarkProcess = async (id) => {
    const response = await callApi({
      url: `preprocessing/bookmark`,
      method: 'post',
      body: id,
    });

    const { status } = response;

    if (status === STATUS_SUCCESS) {
      fetchProcessList();
    }
  };

  const handleModal = () => {
    dispatch(
      openModal({
        modalType: 'ADD_DATASET_PREPROCESS',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              fetchProcessList();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspace_id: wid,
        },
      }),
    );
  };

  useEffect(() => {
    fetchProcessList();
  }, []);

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>{`${t('data.label')} ${t(
        'preprocess.label',
      )}`}</div>
      <CardList>
        <CreateCard
          label={`${t('preprocess.label')} ${t('create.label')}`}
          handleCreateCard={handleModal}
          minWidth={'302px'}
          height={'422px'}
        />
        {processList
          .sort((a, b) => b.isBookmark - a.isBookmark)
          .map(
            ({
              owner,
              name,
              desc,
              gpu,
              cpu,
              ram,
              instance,
              id,
              access,
              jobStatus,
              time,
              type,
              instanceAllocate,
              isBookmark,
              userList,
            }) => (
              <ProcessCard
                key={id}
                id={id}
                owner={owner}
                name={name}
                desc={desc}
                gpu={gpu}
                cpu={cpu}
                ram={ram}
                instance={instance}
                access={access}
                instanceAllocate={instanceAllocate}
                deleteProcess={deleteProcess}
                fetchProcessList={fetchProcessList}
                jobStatus={jobStatus}
                time={time}
                type={type}
                isBookmark={isBookmark}
                bookmarkProcess={bookmarkProcess}
                userList={userList}
                loginUser={loginUser}
              />
            ),
          )}
      </CardList>
    </div>
  );
};

export default UserDatasetPreprocessContent;
