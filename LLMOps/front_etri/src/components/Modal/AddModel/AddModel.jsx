import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Radio, Textarea } from '@tango/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import { calNameValidate } from '../AddPlayground/AddPlayground';
import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import SearchComponent from '../FineTuningDataUploadModal/SearchComponent';
import NewStyleModalFrame from '../NewStyleModalFrame';
import { initialModelData } from './Items';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddModel.module.scss';

import IconAllmModel from '@src/static/images/icon/ic-allm-model.svg';
import IconVersion from '@src/static/images/icon/ic-allm-version.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';

const cx = classNames.bind(style);

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

// Hugging Submenu options
// value=1 Hugging Face / value=0 GenAI Platform / value=2 External Training (외부 협력기관 컨테이너)
const accessTypeOptions = [
  {
    label: 'Single',
    value: 1,
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
  {
    label: 'Multimodal',
    value: 'multimodal',
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
  {
    label: 'GenAI Platform',
    value: 0,
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
  {
    label: 'External Training',
    value: 2,
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
];

const calFooterMessage = (
  modelName,
  type,
  huggingData,
  huggingData2,
  modelBaseData,
  versionData,
  firstNameInput,
  t,
) => {
  const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

  // if (!firstNameInput.current) return ' ';
  if (modelName === '') {
    return t('modelName.message');
  } else if (forbiddenChars.test(modelName)) {
    return t('newNameRule.message');
  }

  // type === 2 → External Training. base model 대신 manifest 선택 (UI 영역에서 별도 검증).
  if (type === 2) {
    return '';
  }

  if (type === 1) {
    if (!huggingData) return t('model.select.message');
  } else if (type === 'multimodal') {
    if (!huggingData || !huggingData2) return t('model.select.message');
  } else {
    if (!modelBaseData) return t('model.select.message');
    if (!versionData) return t('version.select.warning.message');
  }

  return '';
};

const accessOption = [
  {
    label: 'public',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: 'private',
    value: 0,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

// ** handler user select
const onSelectUser = (setState, list) => {
  setState(list);
};

const AddModel = ({ data, type }) => {
  const { workspaceId, refresh } = data;
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [loadType, setLoadType] = useState(1); // 1=HF, 0=GenAI, 2=External
  // External training 모드 — manifest dropdown (BFF /api/external/manifests).
  const [externalManifests, setExternalManifests] = useState([]);
  const [externalManifestKey, setExternalManifestKey] = useState('');
  const [externalManifestsLoading, setExternalManifestsLoading] = useState(false);
  const [huggingList, setHuggingList] = useState(null);
  const [huggingList2, setHuggingList2] = useState(null);
  const [modelBaseList, setModelBaseList] = useState([]);
  const [versionList, setVersionList] = useState([]);
  const [loading, setLoading] = useState(false);

  const [modelData, setModelData] = useState({
    modelName: '',
    modelDesc: '',
  });

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

  const [huggingData2, setHuggingData2] = useState({
    keyword: '',
    token: '',
    private: 0,
    selectedModel: null,
    selectedOption: {
      label: 'Public',
      value: 'public',
    },
  });
  const [modelBaseData, setModelBaseData] = useState(initialModelData);

  const [versionData, setVersionData] = useState(initialModelData);

  const [selectedAccessType, setSelectedAccessType] = useState(1);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);
  const [userList, setUserList] = useState([]);
  const [selectedUserList, setSelectedUserList] = useState([
    // 수정 시 사용 & 멀티셀렉 렌더링시 setUserList에 넣어줌.
  ]);

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const accessRadioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  const onChange = (label, value) => {
    setModelData((prev) => ({
      ...prev,
      [label === 'name' ? 'modelName' : 'modelDesc']: value,
    }));
  };

  // hugging list 선택
  const onSelectHugging = (name, id) => {
    if (id === 'second') {
      setHuggingData2((prev) => ({
        ...prev,
        selectedModel: name,
      }));
    } else {
      setHuggingData((prev) => ({
        ...prev,
        selectedModel: name,
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

  // 외부 학습 manifest 목록 fetch — 라디오에서 'External Training' 처음 선택 시 호출.
  const getExternalManifests = useCallback(async () => {
    if (externalManifests.length > 0) return; // 이미 캐시됨
    setExternalManifestsLoading(true);
    const response = await callApi({
      url: 'external/manifests',
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS && Array.isArray(result)) {
      const active = result.filter((m) => m && m.is_active !== false);
      setExternalManifests(active);
      if (active.length > 0 && !externalManifestKey) {
        const first = active[0];
        setExternalManifestKey(
          `${first.manifest_name}@${first.manifest_version}`,
        );
      }
    } else {
      errorToastMessage(error, message);
    }
    setExternalManifestsLoading(false);
  }, [externalManifests.length, externalManifestKey]);

  // 모달 Radio
  const radioBtnHandler = (value) => {
    const radioType = value === 'multimodal' ? 'multimodal' : parseInt(value, 10);
    setLoadType(radioType);
    if (radioType === 0) {
      getModelBaseModel();
    } else if (radioType === 2) {
      getExternalManifests();
    }
  };

  const { t } = useTranslation();

  const onClickHuggingSubMenu = (selectedItem, id) => {
    if (selectedItem.value === 'private') {
      openTokenModal(selectedItem, id);
    } else {
      if (id === 'second') {
        setHuggingData2((prev) => ({
          ...prev,
          private: 0,
          selectedOption: selectedItem,
        }));
      } else {
        setHuggingData((prev) => ({
          ...prev,
          private: 0,
          selectedOption: selectedItem,
        }));
      }
    }
  };

  /**
   * Hugging Token 모달
   */
  const openTokenModal = async (selectedItem, id) => {
    dispatch(
      openModal({
        modalType: 'HUGGINGFACE_TOKEN_MODAL',
        modalData: {
          onSubmit: (token) => {
            if (id === 'second') {
              setHuggingData2((prev) => ({
                ...prev,
                token,
                private: 1,
                selectedOption: selectedItem,
              }));
            } else {
              setHuggingData((prev) => ({
                ...prev,
                token,
                private: 1,
                selectedOption: selectedItem,
              }));
            }
            dispatch(closeModal('HUGGINGFACE_TOKEN_MODAL'));
          },
          postHuggingFace: id === 'second' ? postHuggingFace2 : postHuggingFace,
        },
      }),
    );
  };

  // model base
  const onClickModelSubMenu = async (selectedItem, type) => {
    if (type === 'first') {
      setModelBaseData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    } else {
      setVersionData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    }
  };

  // POST Submit Model
  const postModel = async () => {
    setLoading(true);
    // External training 분기 — manifest_name/version 만 보내고 huggingface 필드는
    // 보내지 않음. backend service.create_model 의 training_type='external' 경로가
    // metadata-only row 를 생성한다.
    let body;
    if (loadType === 2) {
      if (!externalManifestKey) {
        errorToastMessage(null, 'manifest required');
        setLoading(false);
        return;
      }
      const [name, version] = externalManifestKey.split('@');
      body = {
        workspace_id: workspaceId,
        description: modelData.modelDesc,
        model_name: modelData.modelName,
        access: selectedAccessType,
        create_user_id: owner.value,
        users_id: userList.map(({ value }) => value),
        training_type: 'external',
        external_manifest_name: name,
        external_manifest_version: version,
      };
    } else if (loadType === 'multimodal') {
      body = {
        workspace_id: workspaceId,
        description: modelData.modelDesc,
        model_name: modelData.modelName,
        huggingface_token: huggingData.token || huggingData2.token || '',
        huggingface_model_id: `${huggingData.selectedModel?.name},${huggingData2.selectedModel?.name}`,
        private: huggingData.private || huggingData2.private || 0,
        access: selectedAccessType,
        create_user_id: owner.value,
        users_id: userList.map(({ value }) => value),
      };
    } else {
      body = {
        workspace_id: workspaceId,
        description: modelData.modelDesc,
        model_name: modelData.modelName,
        huggingface_token: huggingData.token,
        huggingface_model_id: huggingData.selectedModel?.name,
        private: huggingData.private,
        access: selectedAccessType,
        commit_model_id: versionData.selectedModel?.id,
        create_user_id: owner.value,
        users_id: userList.map(({ value }) => value),
      };
    }

    const response = await callApi({
      url: `models`,
      method: 'post',
      body,
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('EDIT_MODEL'));
      dispatch(closeModal('ADD_MODEL'));
      refresh();
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  // 1. Private 했는데 이후에 검색에서

  // 2. 토큰 모달 안끝남

  // POST Hugging Data
  const postHuggingFace = useCallback(
    async ({ keyword = '', token } = {}) => {
      const body = {
        model_name: keyword,
        huggingface_token: token ? token : huggingData.token,
        private: huggingData.private,
      };

      setHuggingData((prev) => ({
        ...prev,
        keyword,
      }));
      const response = await callApi({
        url: `models/option/huggingface-models`,
        method: 'post',
        body,
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        const formattedResult = result.map((item) => ({
          name: item,
        }));

        setHuggingList(formattedResult);
      } else {
        errorToastMessage(error, message);
      }
    },
    [huggingData.private, huggingData.token],
  );

  // POST Hugging Data 2
  const postHuggingFace2 = useCallback(
    async ({ keyword = '', token } = {}) => {
      const body = {
        model_name: keyword,
        huggingface_token: token ? token : huggingData2.token,
        private: huggingData2.private,
      };

      setHuggingData2((prev) => ({
        ...prev,
        keyword,
      }));
      const response = await callApi({
        url: `models/option/huggingface-models`,
        method: 'post',
        body,
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        const formattedResult = result.map((item) => ({
          name: item,
        }));

        setHuggingList2(formattedResult);
      } else {
        errorToastMessage(error, message);
      }
    },
    [huggingData2.private, huggingData2.token],
  );

  // GET ModelBase - model
  const getModelBaseModel = async ({ keyword = '' } = {}) => {
    setModelBaseData((prev) => ({
      ...prev,
      keyword,
    }));

    let url = `models/option/models?workspace_id=${workspaceId}&search=${keyword}`;

    const response = await callApi({
      url,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setModelBaseList(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  // GET ModelBase - version
  const getModelBaseVersion = async ({ keyword = '', id } = {}) => {
    setVersionData((prev) => ({
      ...prev,
      keyword,
    }));
    let url = `models/option/commit-models?model_id=${
      id ? id : modelBaseData.selectedModel.id
    }&search=${keyword}`;

    const response = await callApi({
      url,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setVersionList(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  const getModelOwner = async (workspace_id) => {
    const res = await callApi({
      url: `models/option/user?workspace_id=${workspace_id}`,
      method: 'get',
    });

    return res;
  };

  useEffect(() => {
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
    postHuggingFace();
    postHuggingFace2();
  }, [postHuggingFace, postHuggingFace2]);

  useEffect(() => {
    const fetchOwnerList = async () => {
      const res = await getModelOwner(workspaceId);
      const { result, status } = res;

      if (status === STATUS_SUCCESS) {
        const ownerListResult = result?.list || result || [];
        setOwnerList(
          (Array.isArray(ownerListResult) ? ownerListResult : []).map(({ id, name }) => ({ value: id, label: name })),
        );
        const loginUser = (Array.isArray(ownerListResult) ? ownerListResult : []).filter(({ name }) => name === userName)[0];

        if (loginUser) {
          setOwner({ label: loginUser.name, value: loginUser.id });
        }
      }
    };
    fetchOwnerList();
  }, [userName, workspaceId]);

  const firstNameInput = useRef(false);
  const footerMessage = calFooterMessage(
    modelData.modelName,
    loadType,
    huggingData.selectedModel,
    huggingData2.selectedModel,
    modelBaseData.selectedModel,
    versionData.selectedModel,
    firstNameInput,
    t,
  );
  const isNameValidate = calNameValidate(modelData.modelName);

  return (
    <NewStyleModalFrame
      title={t('createModel.label')}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: () => {
          postModel();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={footerMessage === ''}
      isResize={true}
      isLoading={loading}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('modelName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('modelName.message')}
            onChange={(e) => {
              firstNameInput.current = true;
              onChange('name', e.target.value);
            }}
            name='workspace'
            value={modelData.modelName}
            status={
              !isNameValidate && firstNameInput.current ? 'error' : 'default'
            }
            isReadOnly={type === 'EDIT_MODEL'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('modelDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('modelDescription.placeholder')}
            value={modelData.modelDesc}
            name='description'
            onChange={(e) => onChange('desc', e.target.value)}
            // status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('modelType.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <div className={cx('radio')}>
            <Radio
              options={accessTypeOptions}
              onChange={(e) => {
                radioBtnHandler(e.currentTarget.value);
              }}
              selectedValue={loadType}
              name='accessType'
              t={t}
            />
          </div>
          <div className={cx('model')}>
            {loadType === 1 && (
              <>
                <SearchComponent
                  key='model'
                  firstData={huggingData}
                  firstList={huggingList}
                  firstSelectedItem={huggingData.selectedModel}
                  onClick={onSelectHugging}
                  onSearchFirst={postHuggingFace}
                  onClickSubMenu={onClickHuggingSubMenu}
                  noSelectedDataMessage={noSelectedDataMessage1}
                  firstIcon={IconSmile}
                  menuOptions={menuOptions}
                  title={{
                    first: 'model.label',
                  }}
                  t={t}
                />
                <span className={cx('hugging-message')}>
                  {t('finetuning.huggingface.message')}
                </span>
              </>
            )}
            {loadType === 'multimodal' && (
              <>
                <SearchComponent
                  key='multimodal'
                  firstData={huggingData}
                  firstList={huggingList}
                  secondData={huggingData2}
                  secondList={huggingList2}
                  firstSelectedItem={huggingData.selectedModel}
                  secondSelectedItem={huggingData2.selectedModel}
                  onClick={onSelectHugging}
                  onSearchFirst={postHuggingFace}
                  onSearchSecond={postHuggingFace2}
                  onClickSubMenu={onClickHuggingSubMenu}
                  noSelectedDataMessage={{
                    first: 'modelSelect.message',
                    second: 'modelSelect.message',
                  }}
                  firstIcon={IconSmile}
                  secondIcon={IconSmile}
                  menuOptions={menuOptions}
                  title={{
                    first: 'Model 1',
                    second: 'Model 2',
                  }}
                  t={t}
                />
                <span className={cx('hugging-message')}>
                  {t('finetuning.huggingface.message')}
                </span>
              </>
            )}
            {loadType === 0 && (
              <SearchComponent
                key='version'
                firstData={modelBaseData}
                firstList={modelBaseList}
                secondData={versionData}
                secondList={versionList}
                firstSelectedItem={modelBaseData.selectedModel}
                secondSelectedItem={versionData.selectedModel}
                firstIcon={IconAllmModel}
                secondIcon={IconVersion}
                onClick={onSelectModel}
                onSearchFirst={getModelBaseModel}
                onSearchSecond={getModelBaseVersion}
                onClickSubMenu={onClickModelSubMenu}
                noSelectedDataMessage={noSelectedDataMessage2}
                title={{
                  first: 'model.label',
                  second: 'version.label',
                }}
                t={t}
              />
            )}
            {loadType === 2 && (
              <div className={cx('external-block')}>
                <label className={cx('external-label')}>
                  {t('externalTraining.start.manifest.label')}
                </label>
                {externalManifestsLoading ? (
                  <div className={cx('external-hint')}>
                    {t('externalTraining.start.loadingManifests.label')}
                  </div>
                ) : externalManifests.length === 0 ? (
                  <div className={cx('external-hint')}>
                    {t('externalTraining.start.noManifests.label')}
                  </div>
                ) : (
                  <select
                    className={cx('external-select')}
                    value={externalManifestKey}
                    onChange={(e) => setExternalManifestKey(e.target.value)}
                  >
                    {externalManifests.map((m) => {
                      const key = `${m.manifest_name}@${m.manifest_version}`;
                      return (
                        <option key={key} value={key}>
                          {key}
                          {m.service_family ? ` — ${m.service_family}` : ''}
                        </option>
                      );
                    })}
                  </select>
                )}
                <div className={cx('external-hint')}>
                  {t('externalTraining.start.subtitle.label')}
                </div>
              </div>
            )}
          </div>
        </InputBoxWithLabel>
      </div>
      <div className={cx('bottom-box')}>
        <div className={cx('content')}>
          <InputBoxWithLabel
            labelText={t('accessType.label')}
            labelSize='large'
            disableErrorMsg
          >
            <FbRadio
              name='accessType2'
              options={accessOption}
              value={selectedAccessType}
              onChange={(e) => {
                accessRadioBtnHandler('accessType2', e.currentTarget.value);
              }}
              isLabelColor
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('content')}>
          <InputBoxWithLabel
            labelText={t('owner.label')}
            labelSize='large'
            disableErrorMsg
          >
            <GrayDropDown
              list={ownerList}
              value={owner}
              handleSelectOption={handleOwner}
              placeholder={t('owner.placeholder')}
              isCloseBorder={false}
              listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
            />
          </InputBoxWithLabel>
        </div>
      </div>
      {selectedAccessType === 0 && (
        <div className={cx('users')}>
          <MultiSelect
            label='users.label'
            listLabel='availableUsers.label'
            selectedLabel='chosenUsers.label'
            list={ownerList} // 초기 목록
            selectedList={selectedUserList} // 초기 선택된 목록
            onChange={({ selectedList }) => {
              onSelectUser(setUserList, selectedList);
            }} // 변경 이벤트
            exceptItem={owner && owner.value} // 목록에서 빠질 아이템
            optional
            style={{ marginTop: '32px' }}
          />
        </div>
      )}
    </NewStyleModalFrame>
  );
};

export default AddModel;
