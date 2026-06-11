import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { InputText, Textarea } from '@tango/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { getRagsOwner, postRag } from '@src/apis/llm/rag';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddRag.module.scss';

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

// * name check
const calIsNameError = (firstInputRef, modalData) => {
  const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;
  if (modalData.ragName === '') {
    return false;
  } else if (forbiddenChars.test(modalData.ragName)) {
    return false;
  }
  return true;
};

// * footer message
const calIsFooterMessage = (modalData, owner, firstInputRef) => {
  const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;
  if (modalData.ragName === '') {
    return 'ragName.placeholder';
  } else if (forbiddenChars.test(modalData.ragName)) {
    return 'newNameRule.message';
  } else if (owner.label === '') {
    return 'owner.placeholder';
  }

  return null;
};

const cx = classNames.bind(style);
const AddRag = ({ data, type }) => {
  const { workspaceId, refresh } = data;
  const dispatch = useDispatch();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const [loadType, setLoadType] = useState(1); // 1 , 0
  // const [footerMessage, setFooterMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [validate, setValidate] = useState(false);

  const [modalData, setModalData] = useState({
    ragName: '',
    ragDesc: '',
  });
  const [selectedAccessType, setSelectedAccessType] = useState(1);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  const onSubmit = async () => {
    setIsLoading(true);
    const response = await postRag({
      workspace_id: workspaceId,
      name: modalData.ragName,
      description: modalData.ragDesc,
      access: selectedAccessType,
      owner_id: owner.value,
    });

    const { result, error, message, status } = response;

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('ADD_RAG'));
      refresh();
    } else {
      errorToastMessage(error, message);
    }
    setIsLoading(false);
  };

  const onChange = (label, value) => {
    setModalData((prevData) => ({
      ...prevData,
      [label === 'name' ? 'ragName' : 'ragDesc']: value,
    }));
  };

  const { t } = useTranslation();

  const firstInputRef = useRef(false);

  const nameError = calIsNameError(firstInputRef, modalData);
  const isNameError = !nameError && firstInputRef.current;
  const footerMessage = calIsFooterMessage(modalData, owner, firstInputRef);

  useEffect(() => {
    const fetchOwnerList = async () => {
      const res = await getRagsOwner(workspaceId);
      const { result, status } = res;

      if (status === STATUS_SUCCESS) {
        setOwnerList(
          result.map(({ id, name }) => ({ value: id, label: name })),
        );
        const loginUser = result.filter(({ name }) => name === userName)[0];
        setOwner({ label: loginUser.name, value: loginUser.id });
      }
    };

    fetchOwnerList();
  }, [userName, workspaceId]);

  return (
    <NewStyleModalFrame
      title={t('createRag.label')}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: () => {
          onSubmit();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!footerMessage}
      isLoading={isLoading}
      isResize={true}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('ragName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('ragName.placeholder')}
            onChange={(e) => {
              firstInputRef.current = true;
              onChange('name', e.target.value);
            }}
            name='workspace'
            value={modalData.ragName}
            status={isNameError ? 'error' : 'default'}
            isReadOnly={type === 'EDIT_RAG'}
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
          labelText={t('ragDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('ragDescription.placeholder')}
            value={modalData.ragDesc}
            name='description'
            onChange={(e) => onChange('desc', e.target.value)}
            // error={descriptionError}
            // status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
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
              name='accessType'
              options={accessOption}
              value={selectedAccessType}
              onChange={(e) => {
                radioBtnHandler('accessType', e.currentTarget.value);
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
    </NewStyleModalFrame>
  );
};

export default AddRag;
