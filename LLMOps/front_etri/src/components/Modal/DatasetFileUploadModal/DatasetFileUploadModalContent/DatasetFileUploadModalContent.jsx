// Components
import DataInputForm from './DataInputForm';

const DatasetFileUploadModalContent = ({
  files,
  folders,
  filesError,
  uploadTypeOptions,
  uploadType,
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
  gitCommend,
  handleWgetForm,
  checkLoading,
}) => {
  return (
    <DataInputForm
      files={files}
      folders={folders}
      filesError={filesError}
      uploadTypeOptions={uploadTypeOptions}
      uploadType={uploadType}
      fileInputHandler={fileInputHandler}
      folderInputHandler={folderInputHandler}
      radioBtnHandler={radioBtnHandler}
      onRemoveFiles={onRemoveFiles}
      onRemoveFolder={onRemoveFolder}
      datasetName={datasetName}
      loc={loc}
      uploadPath={uploadPath}
      textInputHandler={textInputHandler}
      testType={testType}
      uploadMethod={uploadMethod}
      handleUploadMethod={handleUploadMethod}
      handleGitForm={handleGitForm}
      handleGitCommand={handleGitCommand}
      handleScpForm={handleScpForm}
      wgetFormError={wgetFormError}
      scpFormError={scpFormError}
      scpErrorMessage={scpErrorMessage}
      gitForm={gitForm}
      scpForm={scpForm}
      wgetForm={wgetForm}
      gitCommend={gitCommend}
      handleWgetForm={handleWgetForm}
      checkLoading={checkLoading}
    />
  );
};

export default DatasetFileUploadModalContent;
