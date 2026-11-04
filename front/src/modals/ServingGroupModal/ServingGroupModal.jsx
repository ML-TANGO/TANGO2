import { useEffect, useState } from 'react';
import { debounce } from 'lodash';

// i18n
import { useTranslation } from 'react-i18next';

// Component
import ServingModalContent from '@src/components/modalContents/ServingModalContent/ServingModalContent';
import { callApi } from '@src/network';

function ServingGroupModal({ type, data: modalData }) {
  const { t } = useTranslation();

  const { workspaceId, groupData } = modalData.data;
  const status = modalData.status;
  const [groupNameStatus, setGroupNameStatus] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [description, setDescription] = useState('');
  const [createButtonStatus, setCreateButtonStatus] = useState(null);

  const validate = (value) => {
    // const regType1 = /^[a-z0-9]+(-[a-z0-9]+)*$/;
    const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

    const regType = !forbiddenChars.test(value);
    if (value === '') {
      return false;
    }
    if (!regType) {
      return true;
    }
    return null;
  };

  const checkDuplicate = debounce(async (value) => {
    const resp = await callApi({
      url: `options/deployments/templates/check-group-name?deployment_template_group_name=${value}&workspace_id=${workspaceId}`,
      method: 'GET',
    });
    if (resp.result.is_duplicated) {
      setGroupNameStatus(t('template.groupModalInput.label'));
    }
    setCreateButtonStatus(() => resp.result.ics_duplicated);
  }, 250);

  const nameInputHandler = (e) => {
    const validation = validate(e.target.value);
    if (validation) {
      setGroupNameStatus(t('newNameRule.message'));
      setCreateButtonStatus(true);
    } else {
      setGroupNameStatus('');
      if (e.target.value !== '') {
        checkDuplicate(e.target.value);
        setCreateButtonStatus(false);
        setGroupNameStatus(false);
      }
    }
    setGroupName(e.target.value);
  };

  const descriptionInputHandler = (e) => {
    setDescription(e.target.value);
  };

  useEffect(() => {
    if (groupData) {
      setGroupName(groupData.name);
      groupData.description && setDescription(groupData.description);
    }
  }, [groupData]);

  return (
    <ServingModalContent
      groupNameStatus={groupNameStatus}
      groupName={groupName}
      description={description}
      nameInputHandler={nameInputHandler}
      descriptionInputHandler={descriptionInputHandler}
      type={type}
      modalData={modalData}
      createStatus={createButtonStatus}
      status={status}
    />
  );
}
export default ServingGroupModal;
