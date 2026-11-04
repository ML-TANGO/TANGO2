import { useState } from 'react';

// Components
import File from '@src/components/molecules/File';
import Folder from '@src/components/molecules/Folder';

// CSS module
import style from './DatasetUploadForm.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const DatasetUploadForm = ({
  t,
  onChange,
  progressRefs,
  datasetName,
  defaultText = true,
}) => {
  const [data, setData] = useState([
    { formData: { files: [], folders: [] } },
    { formData: { files: [], folders: [] } },
  ]);
  let _folderName = '';
  // 인풋 폴더 이벤트 핸들러
  const folderInputHandler = (nFiles, key) => {
    const newFiles = [];
    const newData = [...data];
    for (let i = 0; i < nFiles.length; i += 1) {
      newFiles.push(nFiles[i]);
    }
    // const files = newFiles;
    const files = [...newData[key].formData.files, ...newFiles];
    const folders = [];
    for (let i = 0; i < files.length; i += 1) {
      const { webkitRelativePath } = files[i];
      const folderName = webkitRelativePath.split('/')[0];
      if (_folderName !== folderName) {
        Object.assign(files[i], { folderName: folderName });
        _folderName = folderName;
      }
      // eslint-disable-next-line no-continue
      if (folders.indexOf(folderName) > -1) continue;
      folders.push(folderName);
    }
    newData[key].formData.files = files;
    newData[key].formData.folders = folders;
    setData(newData);
    onChange(newData);
  };

  // 인풋 파일 이벤트 핸들러
  const fileInputHandler = (files, key) => {
    const newFiles = [];
    for (let i = 0; i < files.length; i += 1) {
      newFiles.push(files[i]);
    }

    const newData = [...data];
    newData[key].formData.files = [...newData[key].formData.files, ...newFiles];
    setData(newData);
    onChange(newData);
  };

  // 파일 삭제 이벤트 핸들러
  const onRemoveFiles = (idx) => {
    const newData = [...data];
    newData[0].formData.files.splice(idx, 1);
    onChange(newData);
  };

  // 폴더 삭제 이벤트 핸들러
  const onRemoveFolder = (name, idx) => {
    const newData = [...data];
    const result = newData[1].formData.files.reduce((acc, cur) => {
      const folderName = cur.webkitRelativePath.split('/')[0];

      if (folderName !== name) acc.push(cur);
      return acc;
    }, []);

    newData[1].formData.files = result;
    newData[1].formData.folders.splice(idx, 1);
    setData(newData);
    onChange(newData);
  };

  return (
    <div className={cx('template-box')}>
      {defaultText && (
        <>
          <p className={cx('form-type')}>
            {`/${datasetName || `{${t('datasetName.label')}}`}/`}
          </p>
          <p className={cx('form-desc')}>{t('topLevelPath.message')}</p>
        </>
      )}

      <div className={cx('form-item')}>
        <div className={cx('upload-box')}>
          <File
            name='files'
            onChange={(f) => {
              fileInputHandler(f, 0);
            }}
            value={data[0].formData.files}
            error={null}
            btnText='addFile.label'
            onRemove={(idx) => {
              onRemoveFiles(idx);
            }}
            fileList={false}
            progressRefs={progressRefs}
            index={0}
          />
        </div>
      </div>
      <div className={cx('form-item')}>
        <div className={cx('upload-box')}>
          <Folder
            name='files'
            onChange={(f) => {
              folderInputHandler(f, 1);
            }}
            value={data[1].formData.folders}
            error={null}
            btnText='addFolder.label'
            onRemove={(name, idx) => {
              onRemoveFolder(name, idx);
            }}
            directory
            disabledErrorText
            folderList={false}
            progressRefs={progressRefs}
            index={1}
          />
        </div>
      </div>
    </div>
  );
};

export default DatasetUploadForm;
