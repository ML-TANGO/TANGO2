import {
  getPlaygroundPrompt,
  getPlaygroundVersion,
} from '@src/apis/llm/playground';
import IconFlag from '@src/static/images/icon/flag-icon.svg';
import IconPrompt from '@src/static/images/icon/prompt-icon.svg';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import { closeModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';
import DoubleDropdown from './DoubleDropdown';

const calMyList = (visibilityValue, list, userName) => {
  if (visibilityValue.value === 0) return list;
  const shallowCopyList = list.slice();
  const myList = shallowCopyList.filter((el) => el.owner === userName);
  return myList;
};

const calVersionList = (visibilityValue, versionList, userName) => {
  const transfromVersionList = versionList.map((el) => {
    return {
      ...el,
      id: el.prompt_commit_name,
      name: el.prompt_commit_name,
    };
  });
  const transformMyVersionList = calMyList(
    visibilityValue,
    transfromVersionList,
    userName,
  );
  return transformMyVersionList;
};

const calFooterMessage = (selectedPrompt, t) => {
  const { prompt_name, prompt_commit_name } = selectedPrompt;
  if (!prompt_name) return t('prompt.warning.label1');
  if (!prompt_commit_name) return t('prompt.warning.label2');
  return '';
};

const getPromptList = async (workspaceId, setPromptList) => {
  const { result, message, status, error } = await getPlaygroundPrompt(
    workspaceId,
  );
  if (status === STATUS_SUCCESS) {
    setPromptList(result);
  } else {
    errorToastMessage(error, message);
  }
};

const getVersionList = async (promptId, setVersionList) => {
  const { result, message, status, error } = await getPlaygroundVersion(
    promptId,
  );
  if (status === STATUS_SUCCESS) {
    setVersionList(result);
  } else {
    errorToastMessage(error, message);
  }
};

const handleReset = (
  visibilityList,
  setIsOpen,
  setVisibilityValue,
  setPromptList,
  setVersionList,
) => {
  setPromptList([]);
  setVersionList([]);
  setVisibilityValue(visibilityList[0]);
  setIsOpen(true);
};

const ImportPromptModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const visibilityList = useMemo(() => {
    return [
      { label: t('total.label'), value: 0 },
      { label: t('me.label'), value: 1 },
    ];
  }, [t]);

  const title = useMemo(() => {
    return `${t('prompt.label')} ${t('getInfo.label')}`;
  }, [t]);

  const { workspaceId } = data;
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [isOpen, setIsOpen] = useState({
    firstIsOpen: true,
    secondIsOpen: false,
  });
  const [visibilityValue, setVisibilityValue] = useState(visibilityList[0]);

  const [selectedPrompt, setSelectedPrompt] = useState({
    prompt_id: '',
    prompt_name: '',
    prompt_commit_name: '',
    prompt_system_message: '',
    prompt_user_message: '',
  });
  const {
    prompt_id,
    prompt_name,
    prompt_commit_name,
    prompt_system_message,
    prompt_user_message,
  } = selectedPrompt;
  const transformPromptValue = {
    id: +prompt_id,
    name: prompt_name,
  };
  const transformVersionValue = {
    id: prompt_commit_name,
    name: prompt_commit_name,
  };

  const footerMessage = calFooterMessage(selectedPrompt, t);

  const handlePromptSelected = async (el, type) => {
    setSelectedPrompt((prev) => {
      return {
        ...prev,
        prompt_id: `${el.id}`,
        prompt_name: el.name,
        prompt_commit_name: '',
        prompt_system_message: '',
        prompt_user_message: '',
      };
    });
    await getVersionList(el.id, setVersionList);
    setIsOpen((prev) => {
      if (type === 'firstIsOpen') {
        return {
          ...prev,
          firstIsOpen: !prev.firstIsOpen,
          secondIsOpen: true,
        };
      } else {
        return {
          ...prev,
          firstIsOpen: false,
          secondIsOpen: true,
        };
      }
    });
  };

  const handleVersionSelected = (el) => {
    setSelectedPrompt((prev) => {
      return {
        ...prev,
        prompt_commit_name: el.prompt_commit_name,
        prompt_system_message: el.system_message,
        prompt_user_message: el.user_message,
      };
    });
  };

  const [promptList, setPromptList] = useState([]);
  const transformPromptList = calMyList(visibilityValue, promptList, userName);

  const [versionList, setVersionList] = useState([]);
  const transformVersionList = calVersionList(
    visibilityValue,
    versionList,
    userName,
  );

  useEffect(() => {
    getPromptList(workspaceId, setPromptList);
    return () => {
      handleReset(
        visibilityList,
        setIsOpen,
        setVisibilityValue,
        setPromptList,
        setVersionList,
      );
    };
  }, [visibilityList, workspaceId]);

  return (
    <NewStyleModalFrame
      submit={{
        text: t('select.label'),
        func: () => {
          dispatch(
            handleSetPlaygroundState({
              type: 'prompt',
              prompt: {
                prompt_id,
                prompt_name,
                prompt_commit_name,
                prompt_system_message,
                prompt_user_message,
              },
            }),
          );
          dispatch(closeModal(type));
        },
      }}
      cancel={{
        text: t('cancel.label'),
        func: () =>
          handleReset(
            visibilityList,
            setIsOpen,
            setVisibilityValue,
            setPromptList,
            setVersionList,
          ),
      }}
      type={type}
      validate={prompt_commit_name && prompt_name}
      isResize={true}
      isMinimize={true}
      title={title}
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <DoubleDropdown
        icon={IconPrompt}
        isOpen={isOpen.firstIsOpen}
        handleIsOpen={(value) => {
          setIsOpen((prev) => ({
            ...prev,
            firstIsOpen: value,
            secondIsOpen: !value,
          }));
        }}
        label={t('prompt.label')}
        placeholder='사용하실 프롬프트 카드를 선택해 주세요.'
        options={transformPromptList}
        value={transformPromptValue}
        handleSelected={(value) => handlePromptSelected(value, 'firstIsOpen')}
        visibilityLabel='생성자'
        visiblityList={visibilityList}
        visibilityValue={visibilityValue}
        handleVisibility={setVisibilityValue}
        outerStyle={{
          borderRadius: '10px 10px 0 0',
          borderBottom: !isOpen.firstIsOpen && 'none',
        }}
        innerStyle={{ borderRadius: '0px', borderBottom: 'none' }}
      />
      <DoubleDropdown
        icon={IconFlag}
        isOpen={isOpen.secondIsOpen}
        handleIsOpen={(value) => {
          setIsOpen((prev) => ({
            ...prev,
            firstIsOpen: false,
            secondIsOpen: value,
          }));
        }}
        label={t('version.label')}
        placeholder='사용하실 프롬프트 카드를 선택해 주세요.'
        options={transformVersionList}
        value={transformVersionValue}
        handleSelected={handleVersionSelected}
        visibilityLabel='생성자'
        visiblityList={visibilityList}
        visibilityValue={visibilityValue}
        handleVisibility={setVisibilityValue}
        outerStyle={{
          borderRadius: `${isOpen.secondIsOpen ? '0px' : '0 0 10px 10px'}`,
        }}
        innerStyle={{ borderRadius: '0 0 10px 10px' }}
      />
    </NewStyleModalFrame>
  );
};

export default ImportPromptModal;
