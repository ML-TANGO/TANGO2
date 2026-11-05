// i18n

// Atom

import { withTranslation } from 'react-i18next';

import ModalFrame from '../ModalFrame';

import classNames from 'classnames/bind';
import style from './DatasetFormModal.module.scss';

const cx = classNames.bind(style);
const DatasetFormModal = ({
  validate,
  data,
  type,
  name,
  nameError,
  description,
  descriptionError,
  accessTypeOptions,
  accessType,
  uploadMethodOptions,
  uploadMethod,
  uploadDataTypeOptions,
  uploadDataType,
  textInputHandler,
  workspaceOptions,
  selectedWorkspace,
  selectInputHandler,
  radioBtnHandler,
  onSubmit,
  selectTemplate,
  defaultTemplate,
  datasetTemplateList,
  datasetTemplate,
  templateFileFolderHandler,
  googleDriveHandler,
  googleAccessTokenHandler,
  builtInModelNamesHandler,
  builtInModelIdHandler,
  droneBm,
  droneStartDate,
  droneEndDate,
  droneArea,
  droneAreaError,
  droneAccess,
  timeRangeHandler,
  droneOptionHandler,
  progressRefs,
  builtInTemplate,
  builtInModelTemplateOptions,
  t,
  footerMessage,
}) => {
  const {
    submit,
    cancel,
    workspaceId,
    contentRender,
    footerRender,
    templateData,
    selectedOption,
  } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const props = {
    headerProps: { type, t },
    contentProps: {
      workspaceId,
      type,
      name,
      textInputHandler,
      nameError,
      description,
      workspaceOptions,
      selectedWorkspace,
      selectInputHandler,
      uploadMethodOptions,
      uploadMethod,
      uploadDataTypeOptions,
      uploadDataType,
      onSubmit,
      selectTemplate,
      defaultTemplate,
      datasetTemplateList,
      datasetTemplate,
      templateFileFolderHandler,
      progressRefs,
      accessTypeOptions,
      accessType,
      radioBtnHandler,
      googleDriveHandler,
      googleAccessTokenHandler,
      builtInModelNamesHandler,
      builtInModelIdHandler,
      descriptionError,
      droneBm,
      droneStartDate,
      droneEndDate,
      timeRangeHandler,
      droneArea,
      droneAreaError,
      droneAccess,
      droneOptionHandler,
      builtInTemplate,
      builtInModelTemplateOptions,
      templateData,
      selectedOption,
      t,
    },
    footerProps: {
      submit: newSubmit,
      submitBtnTestId: 'dataset-create-btn',
      cancel,
      type,
      validate,
      t,
      footerMessage,
    },
  };

  const title =
    type === 'CREATE_DATASET'
      ? t('createDataset.label')
      : t('editDatasetForm.title.label');

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      headerTitle={title}
      title={title}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
      validate={validate}
      customStyle={{
        width: '664px',
      }}
    >
      {/* <div className={cx('form')}> */}
      {contentRender && contentRender(props.contentProps)}
      {/* </div> */}
    </ModalFrame>
  );
};

export default withTranslation()(DatasetFormModal);
