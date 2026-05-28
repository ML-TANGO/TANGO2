// Components
import { Modal } from '@jonathan/ui-react';

import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import DockerImageDeleteModalContent from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModalContent';
import DockerImageDeleteModalFooter from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModalFooter';
import DockerImageDeleteModalHeader from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModalHeader';

// module
import { closeModal } from '@src/store/modules/modal';

function DockerImageDeleteModalContainer({ data: modalData }) {
  const dispatch = useDispatch();
  const { selectedRows } = modalData.data;
  const [thisWorkspace, setThisWorkspace] = useState([]);
  const [allWorkspace, setAllWorkspace] = useState([]);
  const [deleteList, setDeleteList] = useState({
    thisList: '',
    allList: '',
  });
  const { t } = useTranslation();

  const deleteListHandler = (listItem) => {
    const { list, selectedList } = listItem;
    setDeleteList({
      thisList: list,
      allList: selectedList,
    });
  };

  useEffect(() => {
    let thisBucket = [];
    let allBucket = [];
    selectedRows?.forEach((data) => {
      if (data.has_permission === 1) {
        allBucket = allBucket.concat([
          ...allWorkspace,
          { label: data.image_name, value: data.id, deleteDisable: true },
        ]);
      } else if (data.has_permission === 2) {
        thisBucket = thisBucket.concat([
          ...thisWorkspace,
          { label: data.image_name, value: data.id },
        ]);
      } else if (data.has_permission === 3) {
        thisBucket = thisBucket.concat([
          ...thisWorkspace,
          { label: data.image_name, value: data.id, deleteDisable: true },
        ]);
      }
    });
    setAllWorkspace(allBucket);
    setThisWorkspace(thisBucket);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRows]);

  const contentProps = {
    list: thisWorkspace,
    selectedList: allWorkspace,
    func: (list) => {
      deleteListHandler(list);
    },
    t,
  };
  const headerPorps = {
    t,
    handleClose: () => {
      dispatch(closeModal('DELETE_DOCKER_IMAGE'));
    },
  };
  const footerProps = {
    close: () => {
      dispatch(closeModal('DELETE_DOCKER_IMAGE'));
    },
    cancel: modalData?.cancel?.text,
    submit: modalData?.submit, // text and func
    deleteList,
    t,
  };

  return (
    <>
      <Modal
        HeaderRender={DockerImageDeleteModalHeader}
        ContentRender={DockerImageDeleteModalContent}
        FooterRender={DockerImageDeleteModalFooter}
        headerProps={headerPorps}
        contentProps={contentProps}
        footerProps={footerProps}
        topAnimation='calc(50% - 277px)'
        windowStyle={{ width: '664px' }}
        headerStyle={{
          padding: '48px 48px 0 48px',
          fontStyle: 'normal',
          fontWeight: 700,
          lineHeight: '24px',
        }}
        contentStyle={{
          color: '#747474',
          fontFamily: 'SpoqaR',
          fontSize: '16px',
          fontStyle: 'normal',
          fontWeight: 700,
          lineHeight: '150%',
          paddingLeft: '48px',
          paddingRight: '48px',
        }}
        footerStyle={{
          padding: '64px 48px 24px',
        }}
      />
    </>
  );
}
export default DockerImageDeleteModalContainer;
