import { withTranslation } from 'react-i18next';

import useComponentExistObserver from '@src/hooks/useComponentExistObserver';

import NewStyleModalFrame from '../NewStyleModalFrame';

const DockerImageFormModal = ({
  validate,
  data,
  type,
  imageName,
  imageNameError,
  imageDesc,
  imageDescError,
  dockerUrl,
  dockerUrlError,
  dockerTag,
  dockerTagError,
  dockerTagOptions,
  dockerNGC,
  dockerNGCError,
  dockerNGCOptions,
  dockerNGCVersion,
  dockerNGCVersionError,
  dockerNGCVersionOptions,
  uploadTypeOptions,
  uploadType,
  files,
  filesError,
  releaseTypeOptions,
  releaseType,
  textInputHandler,
  multiSelectHandler,
  wsList,
  prevSelectedWsList,
  selectedWsListError,
  fileInputHandler,
  selectInputHandler,
  radioBtnHandler,
  progressRef,
  onSubmit,
  onRemove,
  commitComment,
  commitCommentError,
  isCommit,
  t,
  footerMessage,
}) => {
  const { submit, cancel, headerRender, contentRender, footerRender } = data;
  const [setRef] = useComponentExistObserver();
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const title =
    type === 'CREATE_DOCKER_IMAGE'
      ? t('createDockerImageForm.title.label')
      : type === 'DUPLICATE_DOCKER_IMAGE'
      ? t('duplicateDockerImageForm.title.label')
      : t('editDockerImageForm.title.label');

  const props = {
    headerProps: {
      type,
      t,
    },
    contentProps: {
      type,
      imageName,
      imageNameError,
      imageDesc,
      imageDescError,
      dockerUrl,
      dockerUrlError,
      dockerTag,
      dockerTagError,
      dockerTagOptions,
      dockerNGC,
      dockerNGCError,
      dockerNGCOptions,
      dockerNGCVersion,
      dockerNGCVersionError,
      dockerNGCVersionOptions,
      uploadTypeOptions,
      uploadType,
      files,
      filesError,
      releaseTypeOptions,
      releaseType,
      textInputHandler,
      multiSelectHandler,
      wsList,
      prevSelectedWsList,
      selectedWsListError,
      fileInputHandler,
      selectInputHandler,
      radioBtnHandler,
      progressRef,
      onRemove,
      commitComment,
      commitCommentError,
      isCommit,
      setRef,
    },
    footerProps: {
      submit: newSubmit,
      submitBtnTestId: 'dockerimage-upload-btn',
      cancel,
      type,
      validate,
      t,
      footerMessage,
    },
  };

  const calFooterMessage = (footerMessage) => {
    if (imageNameError) return t(imageNameError);
    if (dockerUrlError) return t(dockerUrlError);
    if (dockerTagError) return t(dockerTagError);
    if (commitCommentError) return t(commitCommentError);
    if (selectedWsListError) return t(selectedWsListError);
    if (footerMessage) return footerMessage;
    return '';
  };

  return (
    <NewStyleModalFrame
      type={type}
      title={title}
      submit={newSubmit}
      cancel={cancel}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={calFooterMessage(footerMessage)}
      customStyle={{ width: '664px' }}
    >
      {contentRender && contentRender(props.contentProps)}
    </NewStyleModalFrame>
  );
};

export default withTranslation()(DockerImageFormModal);
