import { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';

// Actions
import {
  closeUploadList,
  deleteUploadInstance,
} from '@src/store/modules/upload';

// Components
import UploadListModalContent from '@src/components/modalContents/UploadListModalContent';
/**
 *
 * @returns
 */

function UploadListModal() {
  const { uploadList } = useSelector((state) => state.upload);

  const [doneCount, setDoneCount] = useState(0);
  const [expand, setExpand] = useState(true);

  const dispatch = useDispatch();

  const closeModal = () => {
    dispatch(closeUploadList());
  };

  const expandHandler = () => {
    setExpand(!expand);
  };

  const uploadDone = () => {
    setDoneCount(doneCount + 1);
  };

  const onDeleteList = (idx) => {
    dispatch(deleteUploadInstance(idx));
  };

  return (
    <UploadListModalContent
      uploadList={uploadList}
      doneCount={doneCount}
      expand={expand}
      closeModal={closeModal}
      expandHandler={expandHandler}
      uploadDone={uploadDone}
      onDeleteList={onDeleteList}
    />
  );
}
export default UploadListModal;
