// Components
import { Fragment, useEffect, useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import {
  Badge,
  Button,
  InputText,
  Selectbox,
  Switch,
} from '@jonathan/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';

import MarkerBtn from '@src/components/atoms/MarkerBtn';
import Tooltip from '@src/components/atoms/Tooltip';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import { toast } from '@src/components/Toast';

import { openModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import DatasetFinder from './DatasetFinder';
// import UploadButton from './UploadButton';
import DatasetMoveCopy from './DatasetMoveCopy';
import EditIcon from './EditIcon';
// import DatasetCheckModalContainer from '@src/components/Modal/DatasetCheckModal/DatasetCheckModalContainer';
import FileBrowserIcon from './FileBrowserIcon';
import Progressbar from './Progressbar';
import Table from './Table';
import Type from './Type';

// Utils
import {
  convertBinaryByte,
  errorToastMessage,
  extractPath,
  numberWithCommas,
} from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './DatasetDetailContent.module.scss';

// Icons
import warningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';

const cx = classNames.bind(style);

const IS_DOWNLOAD =
  import.meta.env.VITE_REACT_APP_IS_DOWNLOAD_DATASET !== 'false';
const IS_PREVIEW =
  import.meta.env.VITE_REACT_APP_IS_PREVIEW_DATASET !== 'false';

function DatasetDetailContent({
  tableLoading,
  refreshLoading,
  workspaceName, // Workspace Name
  datasetName, // Dataset Name 값
  datasetDesc, // Dataset Description 값
  dirCount, // 폴더 전체 개수
  fileCount, // 현재 경로의 파일수
  totalFileCount, // 파일 전체 개수
  totalSize, // 파일 전체 사이즈
  accessType, // access type 값
  fileList, // 파일 목록
  onSelect, // 테이블의 row 체크박스 선택 이벤트
  toggledClearRows, // 해당 값이 바뀔 때 테이블에서 체크된 row 초기화 (모두 체크 해제)
  keyword, // 키워드
  datasetId,
  onSearchKeyChange,
  searchKey,
  fileType,
  permissionLevel,
  onSearch,
  onClear,
  onTypeChange,
  openDeleteConfirmPopup,
  selectedRows,
  onChangePage,
  onChangeRowsPerPage,
  onUpdate,
  onUpdateName,
  goBack,
  onRowClick,
  tree,
  path,
  pathChangeHandler,
  pathClickHandler,
  pathInputVal,
  setPath,
  historyBack,
  historyForward,
  paginationResetDefaultPage,
  onFileUpload, // 파일 업로드 이벤트
  onCreateFolder, // 폴더 생성 이벤트
  onGitHubClone, // 깃허브 클론 이벤트
  onGoogleDriveUpload, // 구글드라이브 업로드 이벤트
  onFileDownload, // 파일 다운로드 이벤트
  downloading, // 다운로드 중
  onDecompressFile, // 파일 압축해제 이벤트
  disabledDecompress, // 파일 압축해제 비활성화
  decompressing, // 파일 압축해제 중
  deleting, // 파일 삭제 중
  autoLabelingProgress,
  onPreview, // 파일 미리보기
  // onSync, // 새로고침
  newFolder, // 이동/복사 새 폴더
  destinationPath, // 이동/복사 목적 경로
  pathSelectHandler, // 목적 경로 선택 이벤트 핸들러
  pathInputHandler, // 새폴더 입력 이벤트 핸들러
  isCopy, // 복사본 만들기 여부
  isCopyCheckHandler, // 복사본 만들기 이벤트 핸들러
  onConfirmMoveCopy, // 복사/이동 확인
  onCancelMoveCopy, // 복사/이동 취소
  onDatabaseUpload, // 한림대용 DB에서 가져오기
  loc, // 경로
  progressValue,
  getFilebrowser,
  postFilebrowser,
  switchHandler,
  browserSwitch,
  switchLoading,
  switchStatus,
  rowClickFetching,
  fromUploadFetching,
}) {
  const filebrowserDisable = accessType === 0 && permissionLevel > 3;

  const { t } = useTranslation();
  const dispatch = useDispatch();

  // ! const memoizedFileList = useMemo(() => fileList, [fileList]);

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(3);

  /**
   * 데이터셋 업로드 임시 폴더 이름
   * 해당 폴더 이름 변경(수정) 불가, 삭제 가능
   * 폴더 안에서는 업로드/생성 불가, 다운로드/삭제 가능
   */
  const tempFolderName = '.jf_tmp';
  const isTempPath = path[1] === tempFolderName;

  /**
   * 권한에 따라 버튼 비활성화
   */
  const isDisabledBtn =
    (Number(accessType) === 1 && Number(permissionLevel) > 4) ||
    (Number(accessType) === 0 && Number(permissionLevel) > 3);

  const searchOptions = [{ label: t('name.label'), value: 'name' }];

  const typeOptions = [
    { label: t('allType.label'), value: 'all' },
    { label: t('folder.label'), value: 'dir' },
    { label: t('file.label'), value: 'file' },
  ];

  /**
   * 적합성 검사 데이터 get
  //  */
  // const getModelCheckData = async () => {
  //   const response = await callApi({
  //     url: `datasets/${datasetId}/built_in_model_compatibility`,
  //     method: 'GET',
  //   });

  //   const { result, status } = response;

  //   if (status === STATUS_SUCCESS) {
  //     setDatasetList(result);
  //   } else {
  //     toast.error('error');
  //   }
  // };

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  // const handleOpenBigDataUpload = () => {
  //   dispatch(
  //     openModal({
  //       modalType: 'BIG_DATA_UPLOAD',
  //       modalData: {
  //         submit: {
  //           text: 'add.label',
  //         },
  //         cancel: {
  //           text: 'cancel.label',
  //         },
  //         datasetName,
  //         datasetId,
  //         loc,
  //       },
  //     }),
  //   );
  // };

  const columns = useMemo(
    () => [
      {
        name: t('type.label'),
        selector: 'type',
        sortable: false,
        maxWidth: '90px',
        cell: ({ type, name }, i) => {
          if (type === 'file') {
            return (
              <div className={cx('type-column')}>
                <Type isFolder={false} name={name} />
                <span className={cx('file-label')}>{t('file.label')}</span>
              </div>
            );
          }

          if (type === 'dir') {
            return (
              <div className={cx('type-column')}>
                <Type isFolder name={name} />
                <span className={cx('file-label')}>{t('folder.label')}</span>
              </div>
            );
          }
        },
      },
      {
        width: '50px',
        selector: '',
        sortable: false,
        cell: (row) => (
          <div className={cx('edit-box')}>
            <EditIcon
              style={{
                opacity: isDisabledBtn || row.name === tempFolderName ? 0.2 : 1,
              }}
              className={cx('edit-icon')}
              onClick={() => {
                if (!isDisabledBtn && row.name !== tempFolderName) {
                  onUpdateName(row);
                }
              }}
            />
          </div>
        ),
        button: true,
      },

      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('name.label')}
            idx={0}
          />
        ),
        selector: 'name',
        sortable: true,
        minWidth: '170px',
        cell: (row, index) => {
          const {
            type,
            name,
            autolabeling_status: autoLabelingStatus,
            is_preview: isPreview,
          } = row;
          let labelTag = '';
          if (autoLabelingStatus) {
            const { progress, percent } = autoLabelingStatus;
            if (progress === 'in progress') {
              labelTag = (
                <Badge
                  customStyle={{ marginLeft: '4px' }}
                  label={`Auto-labeling-${percent}%`}
                  type='green'
                />
              );
            } else if (progress === 'finish') {
              labelTag = (
                <Badge
                  customStyle={{ marginLeft: '4px' }}
                  label='Labeling-Done'
                  type=''
                />
              );
            }
          }
          return (
            <div
              onClick={(e) => {
                if (type === 'dir') {
                  onRowClick(row);
                }
              }}
            >
              {type === 'dir' || !IS_PREVIEW ? (
                <span className={cx('col-name')} title={name}>
                  {name}
                </span>
              ) : (
                <span
                  className={(cx('col-name'), isPreview ? 'preview-link' : '')}
                  title={isPreview ? t('preview.title.label') : ''}
                  onClick={() => {
                    isPreview && onPreview(name, index);
                  }}
                  style={{
                    display: 'block',
                    // overflow: 'hidden',
                    // whiteSpace: 'nowrap',
                    // textOverflow: 'ellipsis',
                    minWidth: '170px',
                    fontFamily: 'SpoqaM',
                    fontSize: '14px',
                  }}
                >
                  {name}
                </span>
              )}
              {labelTag}
            </div>
          );
        },
      },

      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('size.label')}
            idx={1}
          />
        ),
        selector: 'size',
        sortable: true,
        minWidth: '290px',
        maxWidth: '370px',
        cell: ({ type, size, upload_info: uploadInfo, fake = false }, idx) => {
          if (uploadInfo) {
            const {
              remain_time: remainTime,
              progress,
              total_size: totalSize,
              upload_size: uploadSize,
              status,
            } = uploadInfo;

            if (parseInt(progress) <= 100) {
              if (status === 'error') {
                <div className={cx('size-cell')}>
                  <Tooltip
                    contents={
                      <div className={cx('tooltip-wrapper')}>
                        <div className={cx('tooltip')}>
                          {t('fileUploadError.message')}
                        </div>
                      </div>
                    }
                    icon={warningIcon}
                    iconCustomStyle={{
                      marginRight: '8px',
                    }}
                    contentsCustomStyle={{
                      border: '0.5px solid #DEE9FF',
                      borderRadius: '10px',
                      boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                      padding: '16px',
                    }}
                  />
                  <Progressbar
                    // value={parseInt(progress)}
                    // remainTime={parseInt(remainTime)}
                    // totalSize={totalSize}
                    // uploadSize={uploadSize}
                    // status={status}
                    // fake={fake}
                    value={parseInt(progress)}
                    remainTime={parseInt(remainTime)}
                    totalSize={totalSize}
                    uploadSize={uploadSize}
                    status={status}
                    fake={fake}
                  />
                </div>;
              }
              return (
                <div className={cx('size-cell')}>
                  <Progressbar
                    // value={parseInt(progress)}
                    // remainTime={parseInt(remainTime)}
                    // totalSize={totalSize}
                    // uploadSize={uploadSize}
                    // status={status}
                    // fake={fake}
                    value={parseInt(progress)}
                    remainTime={parseInt(remainTime)}
                    totalSize={totalSize}
                    uploadSize={uploadSize}
                    status={status}
                    fake={fake}
                  />
                </div>
              );
            }
          }
          if (type === 'file') {
            return (
              <span
                title={`${numberWithCommas(size)} Bytes`}
                className={cx('size-cell')}
              >
                {convertBinaryByte(size)}
              </span>
            );
          }
          return '';
        },
      },

      {
        name: t('modifier.label'),
        selector: 'modifier',
        sortable: false,
        maxWidth: '180px',
        cell: ({ modifier }) => {
          return <span className={cx('modifier')}>{modifier}</span>;
        },
      },
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('updatedAt.label')}
            idx={2}
          />
        ),
        selector: 'modified',
        sortable: true,
        maxWidth: '180px',
        cell: ({ modified }) => {
          return convertLocalTime(modified);
        },
      },
      // {
      //   name: t('changeName.label'),
      //   minWidth: '130px',
      //   maxWidth: '140px',
      //   cell: (row) => (
      //     <>
      //       <EditIcon
      //         style={{
      //           opacity: isDisabledBtn || row.name === tempFolderName ? 0.2 : 1,
      //         }}
      //         className={cx('edit-icon')}
      //         onClick={() => {
      //           if (!isDisabledBtn && row.name !== tempFolderName) {
      //             onUpdateName(row);
      //           }
      //         }}
      //       />
      //     </>
      //     // <img
      //     //   src='/images/icon/00-ic-basic-pen.svg'
      //     //   alt='change name'
      //     //   className='table-icon'
      //     //   style={{
      //     //     opacity: isDisabledBtn || row.name === tempFolderName ? 0.2 : 1,
      //     //   }}
      //     //   onClick={() => {
      //     //     if (!isDisabledBtn && row.name !== tempFolderName) {
      //     //       onUpdateName(row);
      //     //     }
      //     //   }}
      //     // />
      //   ),
      //   button: true,
      // },
    ],
    [
      t,
      clickedIdxHandler,
      sortClickFlag,
      isDisabledBtn,
      onUpdateName,
      onRowClick,
      onPreview,
    ],
  );

  const filterList = (
    <Fragment>
      <Selectbox
        size='medium'
        list={typeOptions}
        selectedItem={fileType}
        onChange={onTypeChange}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
      />
    </Fragment>
  );

  const topButtonList = (
    <Fragment>
      <Button
        type='primary-reverse'
        customStyle={{ border: '1px solid #2d76f8', fontFamily: 'SpoqaB' }}
        onClick={onCreateFolder}
        disabled={isDisabledBtn || isTempPath}
      >
        {t('folderCreate.label')}
      </Button>
      <Button
        type='primary-reverse'
        customStyle={{ border: '1px solid #2d76f8', fontFamily: 'SpoqaB' }}
        onClick={onFileUpload}
      >
        {t('uploadDataLess100MB.label').split('\n')[0]}
        <br />
        {t('uploadDataLess100MB.label').split('\n')[1]}
      </Button>
      {/* <Button
        type='primary-reverse'
        customStyle={{ border: '1px solid #2d76f8', fontFamily: 'SpoqaB' }}
        onClick={handleOpenBigDataUpload}
      >
        {t('uploadDataUpper100MB.label').split('\n')[0]}
        <br />
        {t('bigDataUpload.label').split('\n')[1]}
      </Button> */}
      {/* <UploadButton
        onFileUpload={onFileUpload}
        onGoogleDrive={onGoogleDriveUpload}
        onGitHubClone={onGitHubClone}
        disabled={isDisabledBtn || isTempPath}
        onDatabaseUpload={onDatabaseUpload}
      /> */}
    </Fragment>
  );

  const bottomButtonList = (
    <Fragment>
      <Button
        type='primary-light'
        onClick={onFileDownload}
        disabled={selectedRows.length === 0 || !IS_DOWNLOAD}
        loading={downloading}
      >
        {t('download.label')}
      </Button>
      <DatasetMoveCopy
        datasetName={datasetName}
        tree={tree}
        newFolder={newFolder}
        targetPath={path}
        destinationPath={destinationPath}
        pathSelectHandler={pathSelectHandler}
        pathInputHandler={pathInputHandler}
        isCopy={isCopy}
        isCopyCheckHandler={isCopyCheckHandler}
        confirmHandler={onConfirmMoveCopy}
        cancelHandler={onCancelMoveCopy}
        disabled={selectedRows.length === 0 || isDisabledBtn}
        tempFolderName={tempFolderName}
        btnCustomStyle={{
          marginRight: '12px',
          // backgroundColor: '#f0f0f0',
          // color: '#3E3E3E',
          // border: 'none',
        }}
      />
      <Button
        type='primary'
        onClick={onDecompressFile}
        disabled={
          selectedRows.length === 0 ||
          disabledDecompress ||
          isDisabledBtn ||
          isTempPath
        }
        loading={decompressing}
      >
        {t('decompression.label')}
      </Button>
      <Button
        type='red-light'
        onClick={openDeleteConfirmPopup}
        disabled={selectedRows.length === 0 || isDisabledBtn}
        loading={deleting}
      >
        {t('delete.label')}
      </Button>
    </Fragment>
  );

  const DatasetFinderWrapper = () => (
    <DatasetFinder
      onChange={pathChangeHandler}
      onClick={pathClickHandler}
      setPath={setPath}
      tree={tree}
      value={pathInputVal}
      back={historyBack}
      forward={historyForward}
      datasetName={datasetName}
      selectComponent={() => {
        return (
          <Selectbox
            size='medium'
            list={typeOptions}
            selectedItem={fileType}
            onChange={onTypeChange}
            customStyle={{
              selectboxForm: {
                width: '184px',
              },
              listForm: {
                width: '184px',
              },
            }}
          />
        );
      }}
      searchComponent={() => {
        return (
          <InputText
            value={keyword}
            type='medium'
            placeholder={t('search.placeholder')}
            leftIcon='/images/icon/ic-search.svg'
            closeIcon='/images/icon/close-c.svg'
            onChange={(e) => {
              onSearch(e?.target.value);
            }}
            onClear={onClear}
            customStyle={{ width: '184px' }}
            disableLeftIcon={false}
            disableClearBtn={false}
          />
        );
      }}
      loc={loc}
    />
  );

  let datasetStatus = '';
  let datasetStatusText = '';
  if (autoLabelingProgress === 'in progress') {
    datasetStatus = 'active';
    datasetStatusText = 'autoLabelingProgress.message';
  } else if (autoLabelingProgress === 'finish') {
    datasetStatus = 'done';
    datasetStatusText = 'autoLabelingDone.message';
  }

  const reTest = (e) => {
    e.preventDefault(e);
  };

  return (
    <div
      id='DatasetDetailContent'
      className={cx('content')}
      onDrag={(e) => reTest(e)}
    >
      <div className={cx('info-header')}>
        <div className={cx('back-to-list')} onClick={() => goBack()}>
          <img
            className={cx('back-btn-image')}
            src='/images/icon/00-ic-basic-arrow-02-left.svg'
            alt='<'
          />
          <span className={cx('back-btn-label')}>
            {t('dataset.backToList.label')}
          </span>
        </div>
        {/* <Button
          type='primary-light'
          onClick={() => {
            onSync();
          }}
          icon={refreshLoading ? loadingIcon : syncIcon}
          iconAlign='left'
        >
          {t('sync.label')}
        </Button> */}
      </div>
      <div className={cx('info-box')}>
        <div className={cx('left')}>
          <div>
            <div className={cx('dataset-name-box')}>
              <div className={cx('dataset-name')}>
                {/* {t('detailsOf.label', { name: datasetName || '-' })} */}
                {datasetName || '-'}
                <span>{t('detailsOf.label', { name: '' })}</span>
              </div>
              {/** 기존에 permissionLevel이 4미만인 유저만 보여줬는데 상시 보여주는걸로 임시변경 */}
              {permissionLevel < 4 && (
                <img
                  src='/images/icon/00-ic-basic-pen.svg'
                  alt='<'
                  className={cx('edit-btn')}
                  onClick={() => onUpdate()}
                />
              )}
            </div>
          </div>
          {/* <div className={cx('annotation')}>
            {IS_MARKER && permissionLevel > 1 && MARKER_VERSION === '1' && (
              <MarkerBtn
                workspaceName={workspaceName}
                datasetId={datasetId}
                datasetName={datasetName}
                disabled={totalFileCount === 0}
              />
            )}
            {datasetStatus !== '' && (
              <div className={cx('progress', datasetStatus)}>
                {t(datasetStatusText)}
              </div>
            )}
          </div> */}
        </div>
        <div className={cx('right')}>
          <div className={cx('dataset-info')}>
            <div className={cx('meta')}>
              <label>{t('accessType.label')}</label>
              <span>
                {Number(accessType) >= 0 ? (
                  Number(accessType) === 1 ? (
                    t('readAndWrite.label')
                  ) : (
                    t('readOnly.label')
                  )
                ) : (
                  <span className={cx('loading')}>Loading...</span>
                )}
              </span>
            </div>

            {/* <div className={cx('meta')}>
              <span>
                {Number(dirCount) >= 0 ? (
                  numberWithCommas(dirCount)
                ) : (
                  <span className={cx('loading')}>Loading...</span>
                )}
              </span>
            </div>
            <div className={cx('meta')}>
              <label>{t('totalNumberOfFiles.label')}</label>
              <span>
                {Number(totalFileCount) >= 0 ? (
                  numberWithCommas(totalFileCount)
                ) : (
                  <span className={cx('loading')}>Loading...</span>
                )}
              </span>
            </div> */}
            <div className={cx('meta')}>
              <label>{t('totalFileCapacity.label')}</label>
              <span>
                {`${convertBinaryByte(totalSize)} 
                   (${numberWithCommas(totalSize)} Bytes)`}
                {/* {Number(totalFileCount) >= 0 ? (
                  `${convertBinaryByte(totalSize)} 
                   (${numberWithCommas(totalSize)} Bytes)`
                ) : (
                  <span className={cx('loading')}>Loading...</span>
                )} */}
              </span>
            </div>
            <div className={cx('meta', 'description')}>
              <label>{t('description.label')}</label>
              <span>{datasetDesc || '-'}</span>
            </div>
          </div>

          {/* <div className={cx('dataset-check-box')}>
            <span className={cx('dataset-check-title')}>
              {t('builtInModelComplianceCheck.label')}
            </span>
            <div className={cx('drop-box')}>
              <Button
                type='primary-light'
                iconAlign='right'
                icon={
                  datasetOpen
                    ? '/images/icon/00-ic-basic-arrow-02-up-blue.svg'
                    : '/images/icon/00-ic-basic-arrow-02-down-blue.svg'
                }
                customStyle={{ width: '140px' }}
                onClick={datasetOpenHandler}
              >
                {t('datasetCheck.label')}
              </Button>
              <div className={cx('check-modal-wrap')}>
                {datasetOpen && (
                  <DatasetCheckModalContainer
                    list={datasetList}
                    closeFunc={datasetCheckCloseHandler}
                  />
                )}
              </div>
            </div>
          </div> */}
        </div>
      </div>
      <div className={cx('filebrowser-box')}>
        <div className={cx('left')}>{topButtonList}</div>
        {/* <div className={cx('filebrowser-left')}> */}
        {/* <button onClick={() => testFunc()}>tttttt</button> */}
        <div className={cx('filebrowser-content')}>
          <div className={cx('icon')}>
            <FileBrowserIcon />
          </div>
          <div className={cx('title')}>Web Filebrowser</div>
          {/* </div> */}
          {/* <div className={cx('filebrowser-right')}> */}
          <div className={cx('run-box')}>
            <Button
              disabled={
                !browserSwitch ||
                switchStatus === 'pending' ||
                switchStatus === 'failed' ||
                switchStatus === 'error' ||
                switchLoading ||
                filebrowserDisable
              }
              type='primary-light'
              size='medium'
              icon={'/images/icon/00-ic-basic-external-link-blue.svg'}
              iconAlign='right'
              customStyle={{
                fontSize: '16px',
                fontFamily: 'SpoqaM',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0px 14px 0px 20px',
              }}
              onClick={() => {
                if (!filebrowserDisable) {
                  getFilebrowser();
                }
              }}
            >
              {t('run.label')}
            </Button>
            {/* </div> */}
          </div>
          <div className={cx('switch-box')}>
            <Switch
              size='large'
              checked={browserSwitch}
              disabled={filebrowserDisable}
              customStyle={
                // switchLoading || switchStatus === 'pending'
                switchStatus === 'pending'
                  ? { backgroundColor: '#ffab31' }
                  : switchStatus === 'failed' || switchStatus === 'error'
                  ? { backgroundColor: '#eb3e2a' }
                  : switchStatus === null
                  ? { backgroundColor: '#c1c1c1' }
                  : {}
              }
              onChange={() => {
                if (
                  // switchStatus === 'pending' ||
                  // switchStatus === 'failed' ||
                  // switchStatus === 'error' ||

                  switchLoading ||
                  filebrowserDisable
                ) {
                  return;
                }
                postFilebrowser();
              }}
            />
          </div>
          {switchStatus === 'pending' && (
            <div className={cx('filebrowser-message')}>
              {t('datasetFileBrowser.pending.message')}
            </div>
          )}
        </div>
      </div>
      <Table
        loading={tableLoading || rowClickFetching || fromUploadFetching}
        finder={DatasetFinderWrapper}
        hideButtons={false}
        // topButtonList={topButtonList}
        bottomButtonList={fileList?.length > 0 && bottomButtonList}
        data={fileList}
        // data={fileList}
        columns={columns}
        totalRows={fileCount}
        onRowClick={onRowClick}
        onSelect={onSelect}
        toggledClearRows={toggledClearRows}
        // defaultSortField='modified'
        paginationServer
        onChangeRowsPerPage={onChangeRowsPerPage}
        onChangePage={onChangePage}
        selectableRowDisabled={({ fake }) => fake === true}
        searchOptions={searchOptions}
        // searchKey={searchKey}
        // keyword={keyword}
        onSearchKeyChange={onSearchKeyChange}
        // selectableRowSelected={(row) =>
        //   selectedRows.some((selected) => selected.name === row.name)
        // }

        {...(fileList.length > 0 && {
          selectableRowSelected: (row) =>
            selectedRows.some((selected) => selected.name === row.name),
        })}
        // filterList={filterList}
        // onSearch={(e) => {
        //   onSearch(e.target.value);
        // }}
        onClear={onClear}
        paginationResetDefaultPage={paginationResetDefaultPage}
        conditionalRowStyles={[
          {
            when: (row) => row.type !== 'dir',
            style: {
              cursor: 'default !important',
            },
          },
        ]}
        onSortHandler={onSortHandler}
      />
    </div>
  );
}

export default DatasetDetailContent;
