import { useState, useEffect } from 'react';
import { Progress } from 'react-sweet-progress';

// Components
import { toast } from '@src/components/Toast';

// Icons
import closeIcon from '@src/static/images/icon/close-c.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './UploadItem.module.scss';
const cx = classNames.bind(style);

function UploadItem({
  setTotalFileWatch,
  setSuccessFunc,
  setFailFunc,
  uploadStatus,
  uploadDone,
  onDeleteList,
  idx,
}) {
  const [visible, setVisible] = useState(true);
  const [groupName, setGroupName] = useState(
    uploadStatus ? uploadStatus.uploadGroupName : '',
  );
  const [totalProgress, setTotalProgress] = useState(
    uploadStatus ? uploadStatus.totalProgress : 0,
  );
  const [uploadedFiles, setUploadedFiles] = useState(
    uploadStatus ? uploadStatus.uploadedList : [],
  );
  const [fileCount, setFileCount] = useState(
    uploadStatus ? uploadStatus.fileCount : 0,
  );

  const visibleHandler = () => {
    setVisible(!visible);
  };

  useEffect(() => {
    if (setTotalFileWatch) {
      setTotalFileWatch(
        ({
          uploadGroupName,
          totalProgress: tProgress,
          fileCount: fCount,
          uploadedList,
        }) => {
          setGroupName(uploadGroupName);
          setTotalProgress(tProgress);
          setUploadedFiles(uploadedList);
          setFileCount(fCount);
        },
      );
    }

    if (setSuccessFunc) {
      setSuccessFunc(() => {
        setVisible(false);
        uploadDone();
      });
    }

    if (setFailFunc) {
      setFailFunc((message) => {
        toast.error(message);
        setVisible(false);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setTotalFileWatch]);

  return (
    <div className={cx('upload-group')}>
      <div className={cx('group-header')} onClick={visibleHandler}>
        <span className={cx('group-name')}>{groupName}</span>
        <div
          className={cx('close-icon')}
          onClick={() => {
            onDeleteList(idx);
          }}
        >
          <img src={closeIcon} alt={`close-${idx + 1}`} />
        </div>
        <div className={cx('total-progress')}>
          <Progress
            percent={totalProgress}
            status={'active'}
            theme={{
              active: {
                symbol: '',
                color: '#02e366',
                trailColor: '#dbdbdb',
              },
              default: {
                symbol: '',
                color: '#c1c1c1',
                trailColor: '#dbdbdb',
              },
            }}
          />
        </div>
        <span className={cx('upload-status')}>
          ({uploadedFiles.length}/{fileCount})
        </span>
        {/* <div className={cx('visible-controller')}>
          <ArrowButton isUp={visible} color='white' onClick={visibleHandler} />
        </div> */}
      </div>
      {visible && (
        <ul className={cx('upload-list')}>
          {uploadedFiles.map(({ fileName, progress }, key) => (
            <li key={key}>
              {fileName} - {progress}%
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default UploadItem;
