// i18n
import { withTranslation } from 'react-i18next';

function DockerImageFormModalHeader({ type, t }) {
  return (
    <>
      {type === 'CREATE_DOCKER_IMAGE'
        ? t('createDockerImageForm.title.label')
        : type === 'DUPLICATE_DOCKER_IMAGE'
        ? t('duplicateDockerImageForm.title.label')
        : t('editDockerImageForm.title.label')}
    </>
  );
}

export default withTranslation()(DockerImageFormModalHeader);
