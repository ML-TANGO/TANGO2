import DeleteIcon from '@src/static/images/icon/00-ic-close-gray.svg';
import WarningIcon from '@src/static/images/icon/ic-upload-warning.svg';
import { memo, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import Spinner from '@src/components/atoms/Spinner';
import FBLoading from '@src/components/organisms/FBLoading';
import Type from '@src/components/pageContents/common/DatasetDetailContent/Type';

import { removeWorker } from '@src/store/modules/uploadLoading';
import useOutsideClick from '@src/hooks/useOutsideClick';
import usePreventDoubleClick from '@src/hooks/usePreventDoubleClick';

import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage, executeWithLogging, formatTime } from '@src/utils';

import UploadProgressbar from './UploadProgressbar';

import classNames from 'classnames/bind';
import style from './UploadDetail.module.scss';

const cx = classNames.bind(style);
const arrowIconPath = '/images/icon/ic-arrow-down-darkgray.svg';
const formatKoreanDateTime = (isoDateTime, t) => {
  const date = new Date(isoDateTime + 'Z');
  const now = new Date();
  const korDate = `${date.getMonth() + 1}${t(
    'month.label',
  )} ${date.getDate()}${t('day.label')}`;
  const hoursDifference = Math.floor((now - date) / (1000 * 60 * 60));
  return { hoursDifference, korDate };
};

const caldateMessage = (hoursDifference, korDate, t) => {
  if (hoursDifference === 0) return t('before.justMoment.label');
  if (hoursDifference < 24)
    return t('before.hour.label', { hour: hoursDifference });
  return korDate;
};

const UploadItem = memo(
  ({ info, uniqueKey, isLoading, datasetName, workspaceId, itemIndex, t }) => {
    const match = useRouteMatch();
    const history = useHistory();
    const dispatch = useDispatch();

    const [loadingItems, setLoadingItems] = useState([]);
    const activeWorkers = useSelector(
      (state) => state.uploadLoading.activeWorkers,
    );

    const onDeleteFile = (id, path, fileName) => {
      return new Promise((resolve, reject) => {
        // 루트일때는 둘다 /

        let newPath = path;
        if (path && path !== '/') {
          newPath = `/${path}/`;
        }

        const key = `${id}:${newPath}:${fileName}`;
        const worker = activeWorkers.get(key); // 리덕스에서 activeWorkers를 가져옴

        if (worker) {
          let timeout = setTimeout(() => {
            // 일정 시간 내에 응답이 없을 경우 강제로 resolve

            worker.terminate(); // 워커 종료
            dispatch(removeWorker(id, newPath, fileName)); // 리덕스 상태에서 워커 제거
            resolve();
          }, 5000);

          // console.log('삭제 명령 전송:', fileName);
          worker.postMessage({ type: 'cancelUpload', fileName });

          worker.onmessage = (event) => {
            if (event.data.status === 'cancelAcknowledged') {
              clearTimeout(timeout); // 타임아웃 클리어
              worker.terminate(); // 워커 종료

              dispatch(removeWorker(id, newPath, fileName)); // 리덕스 상태에서 워커 제거
              resolve();
            }
          };
        } else {
          dispatch(removeWorker(id, newPath, fileName)); // 워커가 없는 경우에도 리덕스 상태에서 제거
          resolve(); // 워커가 없을 경우에도 resolve
        }
      });
    };

    const {
      dataset_id: dId,
      workspace_name: workspaceName,
      // workspace_id: workspaceId,

      status,
      fileName,
      upload_size: uploadSize,
      total_size: totalSize,
      datetime,
      path,
      type,
      progress,
      remain_time: remianTime,
      upload_type: uploadType,
    } = info;

    // path, file name 분리 함수
    const extractPathAndFileName = (fullPath) => {
      // 백엔드에서 path값라는 값에 파일네임까지 포함되어 오기때문에 path, filename을 나눠야합니다.

      const parts = fullPath.split('/');

      // 배열에서 마지막 부분은 파일명
      const originFileName = parts.pop();

      // 나머지 부분은 경로
      const originPath = parts.join('/');

      return { originPath, originFileName };
    };

    const { originPath, originFileName } = extractPathAndFileName(path);

    // const originPath = '';
    // const originFileName = 'testowen3.txt';

    const handleItemClick = (datasetName, itemIndex) => {
      // 삭제
      // 워커 종료와 삭제 api 사용 (삭제 api는 기존 선택해서 삭제하는 api 그대로 사용)
      const uniqueKey = `${datasetName}-${itemIndex}`; // 고유한 키 조합 (ui 스피너용)
      // ! 여기서 종료 로직 그이후에.. 여러개 삭제랑 하나 삭제랑 다 다르게 가야함

      const body = {};

      body.data_list = [originFileName];
      // 로딩 시작 로직
      setLoadingItems((prev) => [...prev, uniqueKey]);
      let workerPath = '/';
      if (originPath && originPath !== '') {
        workerPath = originPath;
        body.path = originPath;
      }

      onDeleteFile(dId, workerPath, originFileName).then(async () => {
        const response = await callApi({
          url: `datasets/${dId}/files`,
          method: 'post',
          body,
        });
        const { status, message, error } = response;

        if (status === STATUS_SUCCESS) {
          // 성공
          setLoadingItems((prev) => prev.filter((key) => key !== uniqueKey));
        }
      });
    };

    const { userName } = useSelector((state) => state.auth, shallowEqual);

    const handleUploadView = useCallback(
      (dId, workspaceId, originPath) => {
        // 클릭해서 해당 업로드 쪽으로 들어가는 로직

        if (isLoading.current) return;

        history.push({
          // pathname: `/user/workspace/${workspaceId}/datasets/${dId}/files`,
          pathname: `/user/workspace/${workspaceId}/datasets/${dId}/files`,
          state: { fromUploadAlarm: true, uploadingPath: `/${originPath}` },
        });
      },
      [isLoading, history, workspaceId],
    );

    const handleDeleteUpload = usePreventDoubleClick(
      async (e, info, datasetName, itemIndex) => {
        //  삭제 이벤트
        e.stopPropagation();

        handleItemClick(datasetName, itemIndex);
        // if (isLoading.current) return;
        // isLoading.current = true;
        // await executeWithLogging(async () => {
        //   const { status, error, errorMessage } = await callApi({
        //     url: 'upload',
        //     method: 'delete',
        //     body: { upload_id: _id },
        //   });
        //   if (!status) {
        //     errorToastMessage(error, errorMessage);
        //   }
        // });
      },
      1000,
    );

    // const { hoursDifference, korDate } = formatKoreanDateTime(
    //   create_datetime.split('.')[0],
    //   t,
    // );

    const testName = 'test123';

    return (
      <li
        className={cx(
          'upload-item',
          // status === 'completed' ? 'completed' : 'uploading',
        )}
        onClick={() => handleUploadView(dId, workspaceId, originPath)}
      >
        <div className={cx('flex-cont')}>
          {isLoading.current && (
            <div className={cx('loading-cont')}>
              <FBLoading />
            </div>
          )}
          <div className={cx('dot', status)} />
          <div className={cx('contents-cont')}>
            <div className={cx('info')}>
              <div className={cx('upload-name')}>
                {/* <div>{`(file)`}</div> */}
                <Type isFolder={uploadType === 'dir' ? true : false} />
                <div>{originFileName}</div>
              </div>
              <div className={cx('size')}>
                {uploadSize} / {totalSize}
              </div>
            </div>
            <div className={cx('progress')}>
              <UploadProgressbar value={progress} status={status} />
              <div className={cx('progress-info')}>
                <div className={cx('item')}>
                  <div className={cx('title')}>{t('progress.label')}</div>
                  <div className={cx('value', status)}>
                    {status === 'error' ? t(status) : `${progress}%`}
                  </div>
                </div>
                <div className={cx('item')}>
                  <div className={cx('title')}>{t('remainingTime.label')}</div>
                  <div className={cx('value')}>{formatTime(remianTime, t)}</div>
                </div>
              </div>
            </div>
          </div>

          {loadingItems.includes(uniqueKey) ? (
            <div className={cx('loading-box')}>
              <Spinner size='sm' color='gray' />
            </div> // ?  로딩 중일 때 표시
          ) : (
            <img
              className={cx('delete-btn')}
              onClick={(e) =>
                handleDeleteUpload(e, info, datasetName, itemIndex)
              }
              src={DeleteIcon}
              alt='deleteIcon'
            /> // ? 평소 표시
          )}
        </div>
        <div className={cx('border')}></div>
      </li>
    );
  },
);

const UploadDetail = ({
  isLoading,
  uploadList,
  handleUploadToggle,
  workspaceId,
}) => {
  const { t } = useTranslation();
  const { ref } = useOutsideClick(handleUploadToggle);

  const [activeIndex, setActiveIndex] = useState(null); // 클릭된 데이터셋 인덱스
  const [activeIndexes, setActiveIndexes] = useState([]);

  const toggleItems = (e, index) => {
    e.stopPropagation();
    setActiveIndexes(
      (prevState) =>
        prevState.includes(index)
          ? prevState.filter((i) => i !== index) // 이미 열려있으면 닫기
          : [...prevState, index], // 열기
    );
  };

  return (
    <div ref={ref} className={cx('detail-cont')}>
      <div className={cx('upload-header')}>
        <h1 className={cx('upload-title')}>{t('datasetUploadStatus.label')}</h1>
        {/* <div className={cx('btn-list')}>
          <button className={cx('delete-btn')} onClick={() => console.log(456)}>
            {t('alldelete.btn')}
          </button>
        </div> */}
      </div>
      {/* <ul className={cx('upload-list')}>
        {testItem.length === 0 && (
          <div className={cx('no-upload-cont')}>
            <p className={cx('no-upload')}>{t('no.upload.label')}</p>
          </div>
        )}
        {testItem.length > 0 &&
          testItem.map((info) => {
            return (
              <UploadItem
                key={info._id}
                info={info}
                isLoading={isLoading}
                workspaceId={workspaceId}
                t={t}
              />
            );
          })}
      </ul> */}

      <div className={cx('dropbox-container')}>
        {uploadList && uploadList.length > 0 ? (
          uploadList.map((dataset, index) => {
            return (
              <div key={index} className={cx('dataset')}>
                <div
                  className={cx(
                    'dataset-name',
                    `${activeIndexes.includes(index) && 'open'}`,
                  )}
                  onClick={(e) => toggleItems(e, index)}
                >
                  <div className={cx('left')}>
                    <div></div>
                    {dataset.datasetName}

                    {/* <span className={cx('item-count')}>
                  {dataset?.items?.length}
                </span> */}
                    <div className={cx('circle', 'red')}>
                      <span>{dataset?.items?.length}</span>
                    </div>
                    {/* <div className={cx('warning')}>
                      <img
                        className={cx('delete-btn')}
                        src={WarningIcon}
                        alt='WarningIcon'
                      />
                    </div> */}
                  </div>
                  <div className={cx('arrow-box')}>
                    <img
                      className={cx('workspace-down-arrow')}
                      src={arrowIconPath}
                      alt='arrow'
                    />
                  </div>
                </div>

                <ul //${activeIndex === index ? 'open' : ''
                  className={cx(
                    'items-list',
                    `${activeIndexes.includes(index) ? 'open' : ''}`,
                  )}
                >
                  {dataset.items.length > 0 &&
                    dataset.items.map((info, itemIndex) => {
                      const uniqueKey = `${dataset.datasetName}-${itemIndex}`;
                      return (
                        <UploadItem
                          key={uniqueKey}
                          info={info}
                          isLoading={isLoading}
                          workspaceId={workspaceId}
                          uniqueKey={uniqueKey}
                          datasetName={dataset.datasetName}
                          itemIndex={itemIndex}
                          t={t}
                        />
                      );
                    })}
                </ul>
              </div>
            );
          })
        ) : (
          <div className={cx('no-data')}>{t('no.upload.label')}</div>
        )}
      </div>
    </div>
  );
};

export default UploadDetail;
