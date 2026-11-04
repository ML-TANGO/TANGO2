// Components
import DataInputForm from './DataInputForm';

const LocalFileFormModalContent = ({
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
    />
  );
};

export default LocalFileFormModalContent;
