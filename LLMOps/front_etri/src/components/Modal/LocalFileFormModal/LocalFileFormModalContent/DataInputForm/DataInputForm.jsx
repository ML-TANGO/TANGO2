// i18n
import { useTranslation } from 'react-i18next';
// Components
import Radio from '@src/components/atoms/input/Radio';
import File from '@src/components/molecules/File';
import Folder from '@src/components/molecules/Folder';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import TextInput from '@src/components/atoms/input/TextInput';

// CSS module
import classNames from 'classnames/bind';
import style from './DataInputForm.module.scss';
const cx = classNames.bind(style);

/**
 * 데이터셋 로컬 파일/폴더 업로드 폼에서 사용되는 필수입력 폼 컴포넌트
 * @param {{
 *    files: Array,
 *    folders: Array,
 *    filesError: string | undefined,
 *    uploadType: number,
 *    uploadTypeOptions: [{ label: 'file.label', value: 0 }, { label: 'folder.label', value: 1 }],
 *    fileInputHandler: Function
 *    folderInputHandler: Function,
 *    radioBtnHandler: Function,
 *    onRemoveFiles: Function,
 *    onRemoveFolder: Function,
 *  }} props
 * @returns
 */
function DataInputForm({
  files,
  folders,
  filesError,
  uploadType,
  uploadTypeOptions,
  fileInputHandler,
  folderInputHandler,
  radioBtnHandler,
  onRemoveFiles,
  onRemoveFolder,
  datasetName,
  loc,
  uploadPath,
  textInputHandler,
}) {
  const { t } = useTranslation();

  return (
    <>
      {/* <div className={cx('row')}>
        <InputBoxWithLabel labelText={t('folderName.label')} labelSize='large'>
          <InputBoxWithLabel
            labelText={`/${datasetName}${loc}`}
            leftLabel
            bgBox
          >
            <TextInput
              label={t('folderName.label')}
              placeholder={t('folderName.placeholder')}
              value={uploadPath}
              name='folderName'
              onChange={textInputHandler}
              autoComplete='off'
              // status={
              //   folderNameError === null
              //     ? ''
              //     : folderNameError === ''
              //     ? 'success'
              //     : 'error'
              // }
              maxLength={50}
              autoFocus={true}
            />
          </InputBoxWithLabel>
        </InputBoxWithLabel>
      </div> */}
      <div className={cx('wrapper')}>
        <div className={cx('row', 'upload-type')}>
          <Radio
            name='uploadType'
            options={uploadTypeOptions}
            value={uploadType}
            onChange={radioBtnHandler}
          />
        </div>
        <div className={cx('row')}>
          {uploadType === 0 ? (
            <File
              name='files'
              onChange={fileInputHandler}
              value={files}
              error={filesError}
              btnText={t('browse.label')}
              onRemove={onRemoveFiles}
            />
          ) : (
            <Folder
              name='files'
              onChange={folderInputHandler}
              value={folders}
              error={filesError}
              btnText={t('browse.label')}
              onRemove={onRemoveFolder}
              directory
            />
          )}
        </div>
      </div>
    </>
  );
}

export default DataInputForm;
