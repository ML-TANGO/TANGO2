import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Radio, Textarea } from '@jonathan/ui-react';

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
import style from './EditModel.module.scss';

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

// 모델 유형 옵션 — AddModel 의 accessTypeOptions 와 동일 taxonomy 로 정렬(2026-07-06 QA(2)).
// 수정 모달에선 read-only 표시 전용: Single(1)/Multimodal('multimodal')/GenAI Platform(0)/Domain(2).
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
    label: 'Domain',
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

  if (type === 1) {
    if (!huggingData) return t('model.select.message');
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

const EditModel = ({ data, type }) => {
  const { workspaceId, refresh, prevModelData } = data;

  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [loadType, setLoadType] = useState(1); // 1 , 0
  const [huggingList, setHuggingList] = useState(null);
  const [modelBaseList, setModelBaseList] = useState([]);
  const [versionList, setVersionList] = useState([]);
  const [loading, setLoading] = useState(false);

  const [modelData, setModelData] = useState({
    modelName: prevModelData?.name ?? '-',
    modelDesc: prevModelData?.description ?? '-',
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
  const [modelBaseData, setModelBaseData] = useState(initialModelData);

  const [versionData, setVersionData] = useState(initialModelData);

  const [selectedAccessType, setSelectedAccessType] = useState(1); //* 받아와야함 박재범

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
  const onSelectHugging = (name) => {
    setHuggingData((prev) => ({
      ...prev,
      selectedModel: name,
    }));
  };

  // get Info list
  const getInfoData = useCallback(async () => {
    const response = await callApi({
      url: `models/fine-tuning/summary?model_id=${prevModelData?.id}`,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setLoadType(); //* 1 - hugging
      const {
        huggingface_model_id: huggingModel,
        commit_model_name: commitModel,
        training_type: trainingType,
      } = result;

      // 유형 판별(2026-07-06 QA(2)): external→Domain(2), comma→Multimodal, commit→GenAI(0), else→Single(1).
      if (trainingType === 'external') {
        setLoadType(2);
      } else if (commitModel && commitModel !== '') {
        setLoadType(0);
        const [commit, version] = commitModel.split('/');
        setModelBaseData((prev) => ({
          ...prev,
          selectedModel: { name: commit },
        }));

        setVersionData((prev) => ({
          ...prev,
          selectedModel: { name: version },
        }));
      } else if (huggingModel && huggingModel.includes(',')) {
        setLoadType('multimodal');
        setHuggingData((prev) => ({
          ...prev,
          selectedModel: { name: huggingModel },
        }));
      } else {
        setLoadType(1);
        setHuggingData((prev) => ({
          ...prev,
          selectedModel: { name: huggingModel },
        }));
      }
    } else {
      errorToastMessage(error, message);
    }
  }, [prevModelData?.id]);

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

  // 모달 Radio
  const radioBtnHandler = (value) => {
    const radioType = parseInt(value, 10);
    setLoadType(radioType);
    if (radioType === 0) {
      getModelBaseModel();
    }
  };

  const { t } = useTranslation();

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

  /**
   * Hugging Token 모달
   */
  const openTokenModal = async (selectedItem) => {
    dispatch(
      openModal({
        modalType: 'HUGGINGFACE_TOKEN_MODAL',
        modalData: {
          onSubmit: (token) => {
            // postHuggingFace({ token });
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
  const putModel = async () => {
    setLoading(true);
    const body = {
      description: modelData.modelDesc, // O
      model_name: modelData.modelName, // O
      workspace_id: workspaceId,
      access: selectedAccessType,
      create_user_id: owner.value,
      user_list: userList.map(({ value }) => value),
      model_id: prevModelData?.id,
    };

    const response = await callApi({
      url: `models`,
      method: 'put',
      body,
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('EDIT_MODEL'));
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
    getInfoData();
  }, [getInfoData, postHuggingFace]);

  useEffect(() => {
    // 박재범

    // 뒤 2개는 필요 없을수도

    const fetchOwnerList = async () => {
      const res = await getModelOwner(workspaceId);
      const { result, status } = res;

      if (status === STATUS_SUCCESS) {
        const newList = result.map(({ id, name }) => ({
          value: id,
          label: name,
        }));

        const loginUser = result.filter(({ name }) => name === userName)[0];

        if (prevModelData) {
          const prevSelectedUsers = (prevModelData.users ?? []).map((v) => {
            return {
              label: v.user_name,
              value: v.user_id,
            };
          });

          // 워크스페이스 전체 사용자 + (그 목록에 없는) 기존 멤버.
          // 이전엔 대칭차집합이라 "워크스페이스 사용자이면서 동시에 모델 멤버"인 사람이
          // 소유자 후보에서 통째로 빠졌다 — 현재 소유자가 멤버이기도 하면 프리필된
          // owner 가 정작 드롭다운 목록에 없는 상태가 된다.
          const mergedOwnerList = [
            ...newList,
            ...prevSelectedUsers.filter(
              (prev) => !newList.some((owner) => owner.value === prev.value),
            ),
          ];

          setOwnerList(mergedOwnerList);

          // 소유자는 id 로 식별한다. 이전엔 create_user_name 문자열 매칭이라
          // 동명이인·개명에 취약했고, 매칭 실패 시 owner 가 undefined 로 빠졌다.
          // (create_user_id 는 BE get_models 가 내려주는 필드 — name 매칭은 하위호환 폴백)
          const prevOwner =
            mergedOwnerList.find(
              (v) => v.value === prevModelData.create_user_id,
            ) ??
            mergedOwnerList.find(
              (v) => v.label === prevModelData.create_user_name,
            );
          if (prevOwner) setOwner(prevOwner);

          // 공개(1)/비공개(0) 원본값으로 프리필. isAccess 는 "내가 접근 가능한가"라는
          // 파생 판정이라 수정 모달을 열 수 있는 사람은 사실상 항상 1 → 그대로 저장하면
          // 비공개 모델이 조용히 공개로 덮인다. access 가 없으면 비공개로 보수 처리.
          setSelectedAccessType(prevModelData.access ?? 0);

          // 멤버 목록을 건드리지 않아도 기존 멤버가 그대로 재전송되도록 초기화한다.
          // BE update_model 은 받은 user_list 로 전량 치환하므로 빈 배열 = 전원 삭제다.
          setUserList(prevSelectedUsers);
        } else {
          setOwner({ label: loginUser.name, value: loginUser.id });
        }
      }
    };
    fetchOwnerList();
  }, [prevModelData, userName, workspaceId]);

  const firstNameInput = useRef(false);
  const footerMessage = calFooterMessage(
    modelData.modelName,
    loadType,
    huggingData.selectedModel,
    modelBaseData.selectedModel,
    versionData.selectedModel,
    firstNameInput,
    t,
  );
  const isNameValidate = calNameValidate(modelData.modelName);

  useEffect(() => {
    // 기존 멤버는 항상 프리필한다. 이전엔 `isAccess === 0` 조건이 붙어 있었지만
    // isAccess 는 "내가 접근 가능한가"라 수정 모달을 연 시점엔 언제나 1 이라
    // 이 분기가 한 번도 실행되지 않았고, 멤버 목록이 늘 빈 채로 보였다.
    // MultiSelect 자체가 비공개일 때만 렌더되므로 항상 채워도 무해하다.
    if (prevModelData?.users) {
      const prevSelectedUsers = prevModelData.users.map((v) => {
        return {
          label: v.user_name,
          value: v.user_id,
        };
      });
      setSelectedUserList(prevSelectedUsers);
    }
  }, [prevModelData]);

  return (
    <NewStyleModalFrame
      title={t('editModel.label')}
      type={type}
      submit={{
        text: t('edit.label'),
        func: () => {
          putModel();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={true}
      isResize={true}
      isLoading={loading}
      isMinimize={true}
      // footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('modelName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('workspaceName.placeholder')}
            onChange={(e) => {
              firstNameInput.current = true;
              onChange('name', e.target.value);
            }}
            name='workspace'
            value={modelData.modelName}
            status={
              !isNameValidate && firstNameInput.current ? 'error' : 'default'
            }
            isReadOnly={true}
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
            placeholder={t('workspaceDescription.placeholder')}
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
              isReadonly
              t={t}
            />
          </div>
          <div className={cx('model')}>
            {/* 2026-07-06 QA(2): 유형별 분기. multimodal/domain 은 read-only 표시(빈 GenAI 피커 오표시 방지) */}
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
                  isEditMode={true}
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
            {loadType === 0 && (
              <>
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
                  isEditMode={true}
                  title={{
                    first: 'model.label',
                    second: 'version.label',
                  }}
                  t={t}
                />
              </>
            )}
            {loadType === 'multimodal' && (
              <span className={cx('hugging-message')}>
                {t('editModel.multimodal.encoders', {
                  vision:
                    (huggingData?.selectedModel?.name || '').split(',')[0] ||
                    '-',
                  llm:
                    (huggingData?.selectedModel?.name || '').split(',')[1] ||
                    '-',
                })}
              </span>
            )}
            {loadType === 2 && (
              <span className={cx('hugging-message')}>
                {t('editModel.domain.sds')}
              </span>
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

export default EditModel;
