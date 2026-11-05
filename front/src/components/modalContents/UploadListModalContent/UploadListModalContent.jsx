// i18n
import { useTranslation } from 'react-i18next';

// Atoms
import Button from '@src/components/atoms/button/Button';
import ArrowButton from '@src/components/atoms/button/ArrowButton';

// Components
import UploadItem from './UploadItem';

// CSS Module
import classNames from 'classnames/bind';
import style from './UploadListModalContent.module.scss';
const cx = classNames.bind(style);

/**
 *
 * @param {{
 *  uploadList: Array<{
 *    fileArr: Array,
 *    fileUploadStatus: Object,
 *    setFailFunc: function,
 *    setFileWatch: function,
 *    setSuccessFunc: function,
 *    setTotalFileWatch: function,
 *    upload: function,
 *  }>,
 *  doneCount: number,
 *  expand: boolean,
 *  closeModal: function,
 *  expandHandler: function,
 *  uploadDone: function,
 * }} props
 * @returns
 */
function UploadListModalContent({
  uploadList,
  doneCount,
  expand,
  closeModal,
  expandHandler,
  uploadDone,
  onDeleteList,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('upload-list-modal')}>
      <div className={cx('upload-list-info')}>
        {doneCount === uploadList.length ? (
          <>
            <span className={cx('info')}>
              {t('uploadComplete.label', { count: uploadList.length })}
            </span>
            <Button size='small' type='secondary' onClick={closeModal}>
              {t('close.label')}
            </Button>
          </>
        ) : (
          <span className={cx('info')}>
            {t('uploading.label', { count: uploadList.length })}
          </span>
        )}
        <ArrowButton isUp={expand} color='white' onClick={expandHandler} />
      </div>
      <div className={cx('upload-group-list', expand && 'expand')}>
        {Array.isArray(uploadList) &&
          uploadList.map((item, key) => (
            <UploadItem
              key={key}
              setTotalFileWatch={item.setTotalFileWatch}
              setSuccessFunc={item.setSuccessFunc}
              setFailFunc={item.setFailFunc}
              uploadDone={uploadDone}
              onDeleteList={onDeleteList}
              idx={key}
            />
          ))}
      </div>
    </div>
  );
}

export default UploadListModalContent;
