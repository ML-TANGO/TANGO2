import {
  postOptionHuggingfaceTokenCheck,
  postRagHuggingFace,
} from '@src/apis/llm/rag';
import { loadModalComponent } from '@src/modal';
import IconAllmModel from '@src/static/images/icon/ic-allm-model.svg';
import IconVersion from '@src/static/images/icon/ic-allm-version.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import { handleRagReset, handleSetRagState } from '@src/store/modules/llmRag';
import { closeModal, openModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

import SearchComponent from '../FineTuningDataUploadModal/SearchComponent';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './RagEmbeddingModal.module.scss';

const cx = classNames.bind(style);

const noSelectedDataMessage1 = {
  first: 'modelSelect.message',
};
const menuOptions = [
  { label: 'Public', value: 'public' },
  { label: 'Private', value: 'private' },
];

const toggleList = [
  { value: 0, label: 'Public' },
  { value: 1, label: 'Private' },
];

const modelListInitial = {
  allm_model_list: [],
  hf_model_list: [],
};

const calFooterMessage = (type, huggingData, t) => {
  if (type === 0) {
    if (!huggingData) return t('model.select.message');
  }

  return '';
};

const ImportPlaygroundModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspaceId, isPrivateToken, type: modelType } = data;

  const { model } = useSelector((state) => state.llmPlayground, shallowEqual);

  const title = useMemo(() => {
    return t('model.import.label');
  }, [t]);

  const modelOptions = useMemo(() => {
    return [
      { label: 'Hugging Face', value: 0 },
      // { label: 'A-LLM MODELBASE', value: 1 },
    ];
  }, []);

  const [modelList, setModelList] = useState(modelListInitial); // allm
  const [modelTypeValue, setModelTypeValue] = useState(0);
  const [versionList, setVersionList] = useState([]);

  const [huggingData, setHuggingData] = useState({
    keyword: '',
    token: '',
    private: 0,
    selectedModel: null,
    selectedOption: {
      label: 'Public',
      value: 'public',
    },
  });

  const { setting, info, instance } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );

  const handleModel = () => {
    const model = {};
    if (modelType === 'embedding') {
      model.embedding_model = huggingData.selectedModel.name;
      if (huggingData.private === 1) {
        model.embedding_token = huggingData.token;
      }
    } else {
      model.reranker_model = huggingData.selectedModel.name;
      if (huggingData.private === 1) {
        model.reranker_token = huggingData.token;
      }
    }

    dispatch(
      handleSetRagState({
        type: 'setting',
        setting: {
          ...setting,
          ...model,
        },
      }),
    );
  };

  /**
   * Hugging Token 모달
   */
  const openTokenModal = async (selectedItem) => {
    dispatch(
      openModal({
        modalType: 'HUGGINGFACE_TOKEN_MODAL',
        modalData: {
          onSubmit: (token) => {
            setHuggingData((prev) => ({
              ...prev,
              token,
              private: 1,
              selectedOption: selectedItem,
            }));

            dispatch(closeModal('HUGGINGFACE_TOKEN_MODAL'));
          },
          apiUrl: 'rags/option/huggingface-token-check',
        },
      }),
    );
  };

  // Hugging sub menu 클릭
  const onClickHuggingSubMenu = (selectedItem) => {
    if (selectedItem.value === 'private') {
      openTokenModal(selectedItem);
    } else {
      setHuggingData((prev) => ({
        ...prev,
        private: 0,
        selectedOption: selectedItem,
      }));
    }
  };

  // POST Hugging Data
  const postHuggingFace = useCallback(
    async ({ keyword = '', token } = {}) => {
      setHuggingData((prev) => ({
        ...prev,
        keyword,
      }));

      const res = await postRagHuggingFace({
        name: keyword,
        token: token ? token : huggingData.token,
        privateValue: huggingData.private,
      });

      const { status, result, message, error } = res;
      if (status === STATUS_SUCCESS) {
        const formattedResult = result.map((item) => ({ name: item }));

        setModelList((prev) => ({
          ...prev,
          huggingModelList: formattedResult,
        }));
      } else {
        errorToastMessage(error, message);
      }
    },
    [huggingData.private, huggingData.token],
  );

  const onSelectHugging = (name) => {
    setHuggingData((prev) => ({
      ...prev,
      selectedModel: name,
    }));
  };

  // ** 0: public / 1: private / 2: 토큰 인증 모달
  const [visibilityValue, setVisiblityValue] = useState(toggleList[0]);

  const handleModelType = (e) => {
    setModelTypeValue(+e.target.value);
  };

  const handleVisibility = useCallback(
    (selectedModel) => {
      if (visibilityValue.value === 0) {
        setVisiblityValue(selectedModel);
      }

      if (isPrivateToken) {
        setVisiblityValue(selectedModel);
      } else {
        setVisiblityValue({ value: 3 });
        dispatch(closeModal(type));
        dispatch(
          openModal({
            modalType: 'HUGGINGFACE_TOKEN_MODAL',
          }),
        );
      }
    },
    [isPrivateToken, visibilityValue.value, dispatch, type],
  );

  useEffect(() => {
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
    postHuggingFace();
  }, [postHuggingFace]);

  const footerMessage = calFooterMessage(
    modelTypeValue,
    huggingData.selectedModel,
    t,
  );

  return (
    <NewStyleModalFrame
      submit={{
        text: t('saveBtn.label'),
        func: () => {
          handleModel();
          dispatch(closeModal(type));
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      type={type}
      // validate={isValidateSaveBtn(instance_list)}
      isResize={true}
      isMinimize={true}
      title={title}
      validate={footerMessage === ''}
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <InputBoxWithLabel
        labelText={t('load.model.label')}
        labelSize='large'
        disableErrorMsg
      >
        <Radio
          name={'model-type'}
          value={modelTypeValue}
          options={modelOptions}
          customStyle={{
            marginBottom: '32px',
          }}
          onChange={handleModelType}
          isLabelColor
        />
        {modelTypeValue === 0 && (
          <SearchComponent
            firstData={huggingData}
            firstList={modelList.huggingModelList}
            firstSelectedItem={huggingData.selectedModel}
            onClick={onSelectHugging}
            onSearchFirst={postHuggingFace}
            onClickSubMenu={onClickHuggingSubMenu}
            noSelectedDataMessage={noSelectedDataMessage1}
            menuOptions={menuOptions}
            firstIcon={IconSmile}
            title={{
              first: 'model.label',
            }}
            t={t}
          />
        )}
        {/* {modelTypeValue === 1 && (
          <SearchComponent
            firstData={modelBaseData}
            firstList={modelList.allmModelList}
            secondData={versionData}
            secondList={versionList}
            firstSelectedItem={modelBaseData.selectedModel}
            secondSelectedItem={versionData.selectedModel}
            onClick={onSelectModel}
            onSearchFirst={getPlaygroundModel}
            onSearchSecond={getModelBaseVersion}
            firstIcon={IconAllmModel}
            secondIcon={IconVersion}
            onClickSubMenu={onClickModelSubMenu}
            noSelectedDataMessage={noSelectedDataMessage2}
            title={{
              first: 'model.label',
              second: 'version.label',
            }}
            t={t}
          />
        )} */}
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
};

export default ImportPlaygroundModal;
