import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import {
  getPlaygroundModels,
  postPlaygroundHugging,
} from '@src/apis/llm/playground';
import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import { closeModal, openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import SearchComponent from '../FineTuningDataUploadModal/SearchComponent';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import IconAllmModel from '@src/static/images/icon/ic-allm-model.svg';
import IconVersion from '@src/static/images/icon/ic-allm-version.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';

const noSelectedDataMessage1 = {
  first: 'modelSelect.message',
};

const noSelectedDataMessage2 = {
  first: 'modelSelect.message',
  second: 'version.select.message',
};

const menuOptions = [
  { label: 'Public', value: 'public' },
  { label: 'Private', value: 'private' },
];

const initialModelData = {
  keyword: '',
  selectedModel: null,
  selectedOption: {
    label: 'total.label',
    value: 'total',
  },
};

const toggleList = [
  { value: 0, label: 'Public' },
  { value: 1, label: 'Private' },
];

const modelListInitial = {
  allm_model_list: [],
  hf_model_list: [],
};

const calFooterMessage = (type, huggingData, modelBaseData, versionData, t) => {
  if (type === 0) {
    if (!huggingData) return t('model.select.message');
  } else {
    if (!modelBaseData) return t('model.select.message');
    if (!versionData) return t('version.select.warning.message');
  }

  return '';
};

const ImportPlaygroundModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspaceId, isPrivateToken } = data;

  const { model } = useSelector((state) => state.llmPlayground, shallowEqual);

  const title = useMemo(() => {
    return t('model.import.label');
  }, [t]);

  const modelOptions = useMemo(() => {
    return [
      { label: 'Hugging Face', value: 0 },
      { label: 'GenAI Platform', value: 1 },
    ];
  }, []);

  const [modelList, setModelList] = useState(modelListInitial); // allm
  const [modelTypeValue, setModelTypeValue] = useState(0);
  const [versionList, setVersionList] = useState([]);
  const [modelBaseData, setModelBaseData] = useState(initialModelData);

  const [versionData, setVersionData] = useState(initialModelData);
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

  // token 취소 누르면 다시 public으로 돌리면 돼
  const getPlaygroundModel = useCallback(
    async ({ keyword = '', token }) => {
      //  hugging, allm model 데이터

      let isMine = modelBaseData.selectedOption.value === 'me';
      if (modelTypeValue === 0) {
        isMine = huggingData.selectedOption.value === 'me';
        setHuggingData((prev) => ({
          ...prev,
          keyword,
        }));
      } else {
        setModelBaseData((prev) => ({
          ...prev,
          keyword,
        }));
      }

      const { result, error, message, status } = await getPlaygroundModels(
        workspaceId,
        keyword,
        isMine,
      );

      if (status === STATUS_SUCCESS) {
        const { hf_model_list, allm_model_list } = result;

        const updatedHfModelList = hf_model_list.map((model) => ({
          ...model,
          name: model.id,
        }));

        const updatedAllmModelList = allm_model_list.map((model) => ({
          ...model,
          create_user_name: model.owner,
          // external 학습 모델은 이름 옆에 [External] 마커 표시 (multi-modal infer)
          name:
            model.training_type === 'external'
              ? `${model.name} [External]`
              : model.name,
        }));

        setModelList(() => {
          return {
            allmModelList: updatedAllmModelList,
            huggingModelList: updatedHfModelList,
          };
        });
      } else {
        errorToastMessage(error, message);
      }
    },
    [
      huggingData.selectedOption.value,
      modelBaseData.selectedOption.value,
      modelTypeValue,
      workspaceId,
    ],
  );

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
          postHuggingFace,
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

  // model base select 함수
  const onSelectModel = (model, type) => {
    if (type === 'first') {
      setModelBaseData((prev) => ({
        ...prev,
        // or ...initialModelData,
        selectedModel: model,
      }));
      setVersionData(initialModelData);
    } else {
      setVersionData((prev) => ({
        ...prev,
        selectedModel: model,
      }));
    }
  };

  // model base sub menu 클릭
  const onClickModelSubMenu = async (selectedItem, type) => {
    if (type === 'first') {
      setModelBaseData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    } else {
      // check
      const isMine = selectedItem.value === 'me';
      getModelBaseVersion({ isMine });
      setVersionData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    }
  };

  // GET ModelBase - version
  const getModelBaseVersion = async ({ keyword = '', id, isMine } = {}) => {
    setVersionData((prev) => ({
      ...prev,
      keyword,
    }));

    const computedIsMine =
      isMine ?? versionData?.selectedOption?.value === 'me';

    const firstModelId = id ? id : modelBaseData.selectedModel?.id;

    if (!firstModelId) return;
    let url = `playgrounds/model/commit?model_id=${firstModelId}&search=${keyword}&is_mine=${computedIsMine}`;

    const response = await callApi({
      url,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const transformedResult = result.map(
        ({ model_commit_name: commitName, ...rest }) => ({
          name: commitName,
          ...rest,
        }),
      );
      setVersionList(transformedResult);
    } else {
      errorToastMessage(error, message);
    }
  };

  // POST Hugging Data
  const postHuggingFace = useCallback(
    async ({ keyword = '', token } = {}) => {
      setHuggingData((prev) => ({
        ...prev,
        keyword,
      }));

      const res = await postPlaygroundHugging({
        keyword,
        token,
        isMine: huggingData.private,
      });

      const { status, result, message, error } = res;
      if (status === STATUS_SUCCESS) {
        const formattedResult = result.map((item) => ({ name: item.id }));

        setModelList((prev) => ({
          ...prev,
          huggingModelList: formattedResult,
        }));
      } else {
        errorToastMessage(error, message);
      }
    },
    [huggingData.private],
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
    getPlaygroundModel(workspaceId, setModelList);
  }, [getPlaygroundModel, workspaceId]);

  useEffect(() => {
    if (huggingData?.token) {
      postHuggingFace({ token: huggingData?.token });
    }
  }, [huggingData?.token, postHuggingFace]);

  const onSearchFirst = useMemo(() => {
    return huggingData.private === 0 ? getPlaygroundModel : postHuggingFace;
  }, [getPlaygroundModel, huggingData.private, postHuggingFace]);

  const footerMessage = calFooterMessage(
    modelTypeValue,
    huggingData.selectedModel,
    modelBaseData.selectedModel,
    versionData.selectedModel,
    t,
  );

  const submitModel = () => {
    if (modelTypeValue === 0) {
      return huggingData?.selectedModel?.name || '';
    }
    return modelBaseData?.selectedModel?.name || '';
  };

  console.log('versionData : ', versionData);

  return (
    <NewStyleModalFrame
      submit={{
        text: t('saveBtn.label'),
        func: () => {
          dispatch(
            handleSetPlaygroundState({
              type: 'model',
              model: {
                ...model,
                model_type: modelTypeValue ? 'commit' : 'huggingface',
                model_huggingface_id: !modelTypeValue
                  ? huggingData.selectedModel.name
                  : null,
                model_allm_id: modelTypeValue
                  ? modelBaseData.selectedModel.id
                  : null,
                model_allm_name: modelTypeValue
                  ? modelBaseData.selectedModel.name
                  : null,
                model_allm_commit_id: modelTypeValue
                  ? versionData.selectedModel.model_commit_id
                  : null,
                model_allm_commit_name: modelTypeValue
                  ? versionData.selectedModel.name
                  : null,
                description: !modelTypeValue
                  ? huggingData.selectedModel.description
                  : versionData.selectedModel.description,
                commit: !modelTypeValue
                  ? huggingData.selectedModel.commit
                  : versionData.selectedModel.name,
                access: !modelTypeValue
                  ? huggingData.selectedModel.access
                  : versionData.selectedModel.access,
                create_datetime: !modelTypeValue
                  ? huggingData.selectedModel.create_datetime
                  : versionData.selectedModel.create_datetime,
                update_datetime: !modelTypeValue
                  ? huggingData.selectedModel.update_time
                  : versionData.selectedModel.update_datetime,
              },
            }),
          );
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
            onSearchFirst={onSearchFirst}
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
        {modelTypeValue === 1 && (
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
        )}
      </InputBoxWithLabel>
    </NewStyleModalFrame>
  );
};

export default ImportPlaygroundModal;
