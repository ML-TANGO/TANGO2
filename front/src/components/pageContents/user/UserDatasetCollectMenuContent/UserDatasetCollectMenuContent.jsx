import React, { useCallback, useEffect, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import CardList from '@src/components/molecules/CardTemplate/CardList';
import CreateCard from '@src/components/molecules/CardTemplate/CreateCard';

import {
  getCollectList,
  postCollectBookMark,
  postDeleteCollectCard,
} from '@src/apis/flightbase/dataset/collect';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import DataCollectCardItem from './DataCollectCardItem';

import classNames from 'classnames/bind';
import style from './UserDatasetCollectMenuContent.module.scss';

const cx = classNames.bind(style);

const calMembers = (inputArray) => {
  return inputArray.map((item) => {
    const key = Object.keys(item)[0]; // 객체의 키를 가져옴
    const value = item[key]; // 해당 키의 값을 가져옴
    return { label: value, value: parseInt(key) }; // 새 객체 생성
  });
};

const getCollectListFunc = async (workspaceId, setCardList) => {
  const { result, message, status } = await getCollectList(workspaceId);
  if (status === STATUS_SUCCESS) {
    const sortList = result.list.sort((a, b) => {
      return b.bookmark - a.bookmark;
    });
    const tranformList = sortList.map((item) => ({
      ...item,
      members: calMembers(item.members),
    }));

    setCardList(tranformList);
  } else {
    toast.error(message);
  }
};

export default function UserDatasetCollectMenuContent() {
  const history = useHistory();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { id: workspaceId } = match.params;
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [cardList, setCardList] = useState([]);

  const handleClickCard = useCallback(
    (e, id, info) => {
      e.stopPropagation();

      const transformUserList = info.members.slice().map((item) => ({
        ...item,
        name: item.label,
        id: item.value,
      }));

      if (info.access === 0) {
        if (userName !== info.owner) {
          const findmemberMe = transformUserList.find(
            ({ label }) => label === userName,
          );
          if (!findmemberMe) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }

      history.push(
        `/user/workspace/${workspaceId}/datasets/collect/${id}/detail`,
      );
    },
    [history, userName, workspaceId],
  );

  const handleDelete = useCallback(
    async (e, id, title) => {
      e.stopPropagation();
      dispatch(
        openConfirm({
          title: 'collect.delete.title',
          content: 'collect.delete.content',
          submit: {
            text: 'delete.label',
            func: async () => {
              const { message, status } = await postDeleteCollectCard(id);
              if (status === STATUS_SUCCESS) {
                await getCollectListFunc(workspaceId, setCardList);
              } else {
                toast.error(message);
              }
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          confirmMessage: title,
        }),
      );
    },
    [dispatch, workspaceId],
  );

  const handleBookMark = useCallback(
    async (e, id, isBookMark) => {
      e.stopPropagation();
      const { status, message } = await postCollectBookMark(id, !isBookMark);
      if (status === STATUS_SUCCESS) {
        await getCollectListFunc(workspaceId, setCardList);
      } else {
        toast.error(message);
      }
    },
    [workspaceId],
  );

  const handleCreateModal = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'DATA_COLLECT_MODAL',
        modalData: {
          workspaceId,
          resetFunc: async () => {
            await getCollectListFunc(workspaceId, setCardList);
          },
        },
      }),
    );
  }, [dispatch, workspaceId]);

  const handleEdit = useCallback(
    (e, id, _, info) => {
      e.stopPropagation();

      const transformUserList = info.members.slice().map((item) => ({
        ...item,
        name: item.label,
        id: item.value,
      }));

      if (info.access === 0) {
        if (userName !== info.owner) {
          const findmemberMe = transformUserList.find(
            ({ label }) => label === userName,
          );
          if (!findmemberMe) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }
      dispatch(
        openModal({
          modalType: 'EDIT_DATA_COLLECT_MODAL',
          modalData: {
            workspaceId,
            dataId: id,
            info,
            members: info.members,
            resetFunc: async () => {
              await getCollectListFunc(workspaceId, setCardList);
            },
          },
        }),
      );
    },
    [dispatch, userName, workspaceId],
  );

  useEffect(() => {
    loadModalComponent('DATA_COLLECT_MODAL');
    getCollectListFunc(workspaceId, setCardList);
  }, [workspaceId]);

  return (
    <div className={cx('collect-menu-cont')}>
      <h1 className={cx('title')}>데이터 수집</h1>
      <CardList>
        <CreateCard
          label={'수집 생성'}
          handleCreateCard={handleCreateModal}
          minWidth={'302px'}
          height={'478px'}
        />
        {cardList.map((info) => {
          const {
            id,
            name,
            bookmark: isBookMark,
            collect_method,
            owner,
            instance_info,
            instance_count,
            dataset_name,
            dataset_path,
            collect_cycle,
            collect_cycle_unit,
            collect_storage_limit,
            collect_storage_unit,
            members,
            access,
          } = info;

          return (
            <DataCollectCardItem
              key={id}
              id={id}
              info={info}
              title={name}
              owner={owner}
              members={members}
              isAccess={access}
              instanceName={instance_info?.instance_name}
              instanceCount={instance_count}
              dataType={collect_method}
              dataset_name={dataset_name}
              dataset_path={dataset_path}
              collect_cycle={collect_cycle}
              collect_cycle_unit={collect_cycle_unit}
              collect_storage_limit={collect_storage_limit}
              collect_storage_unit={collect_storage_unit}
              gpu_name={instance_info?.gpu_name}
              isBookMark={isBookMark}
              gpu_allocate={instance_info?.gpu_allocate}
              cpu_allocate={instance_info?.cpu_allocate}
              ram_allocate={instance_info?.ram_allocate}
              handleDelete={handleDelete}
              handleEdit={handleEdit}
              handleBookMark={handleBookMark}
              handleClickCard={handleClickCard}
            />
          );
        })}
      </CardList>
    </div>
  );
}
