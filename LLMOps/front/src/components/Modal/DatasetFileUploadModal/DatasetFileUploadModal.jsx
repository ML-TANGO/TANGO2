// i18n

// Atom
import { Modal } from '@jonathan/ui-react';

import { withTranslation } from 'react-i18next';

const DatasetFileUploadModal = (prop) => {
  const {
    headerRender,
    contentRender,
    footerRender,
    cancel,
    submit,
    datasetName,
    loc,
  } = prop.data;

  const {
    fileInputHandler,
    files,
    folderInputHandler,
    folders,
    isValidate,
    onRemoveFiles,
    onRemoveFolder,
    onSubmit,
    radioBtnHandler,
    uploadTypeOptions,
    uploadType,
    type,
    footerMessage,
    uploadPath,
    textInputHandler,
    uploadLoading,
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
  } = prop;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };
  const modalContentsStyle = {
    headerStyle: {
      padding: '20px 48px 20px',
      borderBottom: '1px solid #DBDBDB',
      margin: 0,
    },
    contentStyle: {
      padding: '24px 48px 0px 48px',
    },
    footerStyle: {
      padding: '12px 48px',
      borderTop: '1px solid #DBDBDB',
    },
  };
  const props = {
    headerProps: {},
    contentProps: {
      fileInputHandler,
      files,
      folderInputHandler,
      folders,
      isValidate,
      onRemoveFiles,
      onRemoveFolder,
      onSubmit,
      radioBtnHandler,
      uploadTypeOptions,
      uploadType,
      datasetName,
      loc,
      uploadPath,
      textInputHandler,
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
    },
    footerProps: {
      cancel,
      submit: newSubmit,
      isValidate,
      type,
      uploadType,
      files,
      footerMessage,
      uploadLoading,
      uploadMethod,
    },
  };
  return (
    <Modal
      HeaderRender={headerRender}
      ContentRender={contentRender}
      FooterRender={footerRender}
      headerProps={props.headerProps}
      contentProps={props.contentProps}
      footerProps={props.footerProps}
      headerStyle={modalContentsStyle.headerStyle}
      contentStyle={modalContentsStyle.contentStyle}
      footerStyle={modalContentsStyle.footerStyle}
      topAnimation='calc(50% - 300px)'
    />
  );
};

export default withTranslation()(DatasetFileUploadModal);
