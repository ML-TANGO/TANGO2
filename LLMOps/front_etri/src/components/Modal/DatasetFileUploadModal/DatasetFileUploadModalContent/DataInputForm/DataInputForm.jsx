// i18n
import { useTranslation } from 'react-i18next';

// Components
import Radio from '@src/components/atoms/input/Radio';
import TextInput from '@src/components/atoms/input/TextInput';
import GitUploadForm from '@src/components/Modal/BigDataUploadModal/GitUploadForm';
import ScpUploadForm from '@src/components/Modal/BigDataUploadModal/ScpUploadForm';
import WgetForm from '@src/components/Modal/BigDataUploadModal/WgetForm';
import File from '@src/components/molecules/File';
import Folder from '@src/components/molecules/Folder';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

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
  testType,
  uploadMethod,
  handleUploadMethod,
  handleGitForm,
  handleGitCommand,
  handleScpForm,
  wgetFormError,
  scpFormError,
  scpErrorMessage,
  gitForm,
  scpForm,
  wgetForm,
  handleWgetForm,
  gitCommend,
  checkLoading,
}) {
  const { t } = useTranslation();

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      // 엔터 키 입력 시 실행할 로직 추가
    }
  };
  return (
    <div className={cx('wrapper')}>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('dataUploadType.label')}
          labelSize='large'
          disableErrorMsg
        >
          <Radio
            name='creator'
            options={[
              {
                label: t('general.label'),
                value: 'general',
              },
              { label: 'scp', value: 'scp' },
              { label: 'wget', value: 'wget' },
              { label: 'git', value: 'git' },
            ]}
            value={uploadMethod}
            onChange={(e) => handleUploadMethod(e.target.value)}
            labelCustomStyle={{
              fontSize: '14px',
            }}
          />
        </InputBoxWithLabel>
      </div>
      {uploadMethod === 'general' && (
        <>
          <div className={cx('row', 'upload-type')}>
            <InputBoxWithLabel
              labelText={t('dataType.label')}
              labelSize='large'
              disableErrorMsg
            >
              <Radio
                name='uploadType'
                options={uploadTypeOptions}
                value={uploadType}
                onChange={radioBtnHandler}
                labelCustomStyle={{
                  fontSize: '14px',
                }}
              />
              <span className={cx('guide')}>
                {`[${t('guide.label')}] `}
                {t('fileNameChange.message', { fileNameList: '' })}
              </span>
            </InputBoxWithLabel>
          </div>
          <div className={cx('row', 'file-box')}>
            {uploadType === 0 ? (
              <File
                name='files'
                onChange={fileInputHandler}
                value={files}
                error={filesError}
                btnText={t('dataset.file.select.label')}
                onRemove={onRemoveFiles}
                checkLoading={checkLoading}
              />
            ) : (
              <Folder
                name='files'
                onChange={folderInputHandler}
                value={folders}
                error={filesError}
                btnText={t('dataset.file.select.label')}
                onRemove={onRemoveFolder}
                checkLoading={checkLoading}
                directory
              />
            )}
          </div>
        </>
      )}
      <div className={cx('form')} onKeyPress={handleKeyPress}>
        {uploadMethod === 'scp' && (
          <ScpUploadForm
            scpForm={scpForm}
            handleScpForm={handleScpForm}
            datasetName={datasetName}
            scpFormError={scpFormError}
            scpErrorMessage={scpErrorMessage}
            loc={loc}
          />
        )}
        {uploadMethod === 'wget' && (
          <WgetForm
            wgetForm={wgetForm}
            handleWgetForm={handleWgetForm}
            datasetName={datasetName}
            wgetFormError={wgetFormError}
            loc={loc}
          />
        )}
        {uploadMethod === 'git' && (
          <GitUploadForm
            gitForm={gitForm}
            handleGitForm={handleGitForm}
            datasetName={datasetName}
            handleGitCommand={handleGitCommand}
            gitCommend={gitCommend}
          />
        )}
      </div>
    </div>
  );
}

export default DataInputForm;
