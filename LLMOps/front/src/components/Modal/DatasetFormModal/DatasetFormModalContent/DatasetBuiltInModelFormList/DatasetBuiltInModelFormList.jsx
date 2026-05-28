import { useRef, useState, useEffect } from 'react';

// Components
import Folder from '@src/components/molecules/Folder';
import File from '@src/components/molecules/File';
import GoogleDrive from '@src/components/atoms/GoogleDrive';

// Icons
import folderIcon from '@src/static/images/icon/border_folder.svg';
import connectIcon from '@src/static/images/icon/connectLine.svg';
import documentIcon from '@src/static/images/icon/ic-document.svg';

// CSS module
import style from './DatasetBuiltInModelFormList.module.scss';
import classNames from 'classnames/bind';

const cx = classNames.bind(style);

const DatasetBuiltInModelFormList = ({
  builtInModelData,
  onChange,
  uploadMethodNumber,
  googleDriveHandler,
  googleAccessTokenHandler,
  builtInModelNamesHandler,
  t,
}) => {
  const categoryText = useRef();
  let folderIndex = 0;
  let fileIndex = 0;
  let childrenLists = [];
  const [uploadedDataName, setUploadedDataName] = useState([]); //올리는 폴더,파일 이름
  const [uploadedDataList, setUploadedDataList] = useState([]); // 올리는 폴더, 파일
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [deleteBtn, setDeleteBtn] = useState(false);
  const [googleDriveData, setGoogleDriveData] = useState([]);

  useEffect(() => {
    const _nameLists = [];
    const _uploadedList = [];
    const _folderData = [];
    for (let data_training_form of builtInModelData) {
      _folderData.push(null);
      _uploadedList.push([]);

      _nameLists.push(data_training_form.name);
    }
    setUploadedDataName(_folderData);
    setGoogleDriveData(_folderData);
    setUploadedDataList(_uploadedList);
    builtInModelNamesHandler(_nameLists);
    onChange([], builtInModelData);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [builtInModelData]);

  useEffect(() => {
    return () => {
      setDeleteBtn(false);
      setSelectedIdx(-1);
    };
  }, [selectedIdx, deleteBtn]);

  const childrenReturn = (children, index, type) => {
    if (children.category.length > 40) {
      categoryText.current.style.marginLeft = '10%';
    }
    return (
      <div
        className={cx('container')}
        style={{
          marginLeft: `${(index - 2) * 32 + 10}px`,
        }}
        key={children.name}
      >
        <div className={cx('line-wrap')}>
          <img className={cx('connectIcon')} src={connectIcon} alt='icon' />
          <img
            className={cx('icon')}
            src={type === 'dir' ? folderIcon : documentIcon}
            alt='icon'
          />
          <span className={cx('name')}>{children.name}</span>
          {children.category && (
            <div ref={categoryText} className={cx('category-text')}>
              {children.category}
            </div>
          )}
        </div>
        <div className={cx('category-description')}>
          {children.category_description}
        </div>
      </div>
    );
  };

  const childrenListForm = (datas) => {
    childrenLists.push(childrenReturn(datas, datas.depth, datas.type));

    if (Array.isArray(datas.children)) {
      for (let i = 0; i < datas.children.length; i++) {
        if (
          datas.children[i].children == null ||
          datas.children[i].children.length === 0
        ) {
          childrenLists.push(
            childrenReturn(
              datas.children[i],
              datas.children[i].depth,
              datas.children[i].type,
            ),
          );
        } else {
          return childrenListForm(datas.children[i]);
        }
      }
    }

    return childrenLists;
  };

  const InputHandler = (nFiles, key, fileName, index) => {
    let _uploadedList = uploadedDataList;
    _uploadedList[index] = nFiles;
    setUploadedDataList(_uploadedList);
    let _folderName = uploadedDataName;
    _folderName[index] = fileName;
    setUploadedDataName(_folderName);
    setSelectedIdx(index);
    onChange(_uploadedList, builtInModelData);
  };

  // 삭제 이벤트 핸들러
  const removeHandler = (builtInModelName) => {
    const removeIndex = uploadedDataName.indexOf(builtInModelName);
    const _uploadedDataName = uploadedDataName;
    const _uploadedList = uploadedDataList;
    _uploadedDataName.splice(removeIndex, 1, null);
    _uploadedList.splice(removeIndex, 1, []);
    setUploadedDataName(_uploadedDataName);
    setUploadedDataList(_uploadedList);
    onChange(_uploadedList, builtInModelData);
    setDeleteBtn(true);
  };

  const googleDriveChange = (data, index) => {
    const _googleDriveData = googleDriveData;
    _googleDriveData[index] = data;
    setGoogleDriveData(_googleDriveData);
    googleDriveHandler(_googleDriveData);
  };

  const googleDriveDelete = (index) => {
    const _googleDriveData = googleDriveData;
    _googleDriveData[index] = null;
    setGoogleDriveData(_googleDriveData);
    googleDriveHandler(_googleDriveData);
  };

  return (
    <>
      {builtInModelData?.map((builtInModelData, index) => {
        if (builtInModelData.name !== '/') {
          if (builtInModelData.type === 'dir') {
            folderIndex += 1;
          } else {
            fileIndex += 1;
          }
          return (
            <div style={{ marginBottom: '10px' }} key={index}>
              {builtInModelData.type === 'dir' ? (
                <>
                  {uploadMethodNumber === 0 ? (
                    <Folder
                      name='files'
                      onChange={(files, folderName) => {
                        InputHandler(files, 1, folderName, index);
                      }}
                      uploadedDataName={uploadedDataName[index]}
                      error={null}
                      btnText={
                        t('folders.label') +
                        ` ${folderIndex} ` +
                        t('upload.label')
                      }
                      directory
                      disabledErrorText
                      folderList={false}
                      index={1}
                      onRemove={(name) => {
                        removeHandler(name);
                      }}
                      uploadedDataIndex={index}
                    />
                  ) : (
                    <GoogleDrive
                      builtInGoogleChange={googleDriveChange}
                      t={t}
                      type={'folder'}
                      uploadedDataIndex={index}
                      googleAccessTokenHandler={googleAccessTokenHandler}
                      googleDriveDelete={googleDriveDelete}
                    />
                  )}
                </>
              ) : (
                <>
                  {uploadMethodNumber === 0 ? (
                    <File
                      name='files'
                      onChange={(f) => {
                        InputHandler(f, 1, f[0].name, index);
                      }}
                      uploadedDataName={uploadedDataName[index]}
                      error={null}
                      btnText={
                        t('files.label') + ` ${fileIndex} ` + t('upload.label')
                      }
                      onRemove={(name) => {
                        removeHandler(name);
                      }}
                      fileList={false}
                      uploadedDataIndex={index}
                    />
                  ) : (
                    <GoogleDrive
                      builtInGoogleChange={googleDriveChange}
                      onChange={googleDriveHandler}
                      t={t}
                      type={'files'}
                      googleAccessTokenHandler={googleAccessTokenHandler}
                      googleDriveDelete={googleDriveDelete}
                      uploadedDataIndex={index}
                    />
                  )}
                </>
              )}
              <div className={cx('text-container')}>
                <span className={cx('type-text')}>
                  {builtInModelData.type === 'dir'
                    ? t('folders.label') + `${folderIndex}`
                    : t('files.label') + `${fileIndex}`}
                  .
                </span>
                <img
                  className={cx('icon')}
                  src={
                    builtInModelData.type === 'dir' ? folderIcon : documentIcon
                  }
                  alt='icon'
                />
                <span className={cx('name-text')}>{builtInModelData.name}</span>
                {builtInModelData.category && (
                  <span className={cx('category')}>
                    {builtInModelData.category}
                  </span>
                )}
              </div>

              <div style={{ marginLeft: '82px' }}>
                <span className={cx('category-description')}>
                  {builtInModelData.category_description}
                </span>
              </div>
              {builtInModelData.type === 'dir' && (
                <div style={{ marginLeft: '40px' }}>
                  {builtInModelData.children.map((data) => {
                    childrenLists = [];
                    return childrenListForm(data);
                  })}
                </div>
              )}
            </div>
          );
        }
        return false;
      })}
    </>
  );
};
export default DatasetBuiltInModelFormList;
