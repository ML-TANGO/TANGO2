import { InputText, Radio, Textarea } from '@tango/ui-react';

import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './FinetuningCommit.module.scss';

const cx = classNames.bind(style);

const FinetuningCommit = ({ data, type }) => {
  const { workspaceId, refresh, modelId, stop } = data;
  const dispatch = useDispatch();

  const [footerMessage, setFooterMessage] = useState('');

  const [validate, setValidate] = useState(false);
  const [loading, setLoading] = useState(false);

  const [modalData, setModalData] = useState({
    commitName: '',
    commitDesc: '',
  });

  const onChange = (label, value) => {
    setModalData((prevData) => ({
      ...prevData,
      [label === 'name' ? 'commitName' : 'commitDesc']: value,
    }));
  };

  const { t } = useTranslation();

  const onSubmit = async () => {
    setLoading(true);
    const body = {
      commit_name: modalData.commitName,
      commit_message: modalData.commitDesc,
      model_id: modelId,
    };

    const commitURL = 'models/commit-models';
    const stopURL = 'models/fine-tuning/stop';
    const response = await callApi({
      url: stop ? stopURL : commitURL,
      method: 'post',
      body,
    });

    const { status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('FINETUNING_COMMIT'));
      refresh();
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  const modalValidate = useCallback(() => {
    const forbiddenChars = /[\\<>:*?"'|:;`{}()^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;
    let validation = 0;
    let footerMessage = '';

    if (modalData.commitName === '') {
      validation++;
      footerMessage = 'commitName.message';
    } else if (forbiddenChars.test(modalData.commitName)) {
      validation++;
      footerMessage = 'newNameRule.message';
    }

    setFooterMessage(footerMessage);
    setValidate(validation === 0);
  }, [modalData]);

  useEffect(() => {
    modalValidate();
  }, [modalData, modalValidate]);

  return (
    <NewStyleModalFrame
      title={t('commit.label')}
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
      validate={validate}
      isResize={true}
      isLoading={loading}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('commitName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('commitName.message')}
            onChange={(e) => onChange('name', e.target.value)}
            name='workspace'
            value={modalData.commitName}
            status={!validate ? 'error' : 'default'}
            isReadOnly={type === 'EDIT_COMMIT'}
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
          labelText={t('commitMessage.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('commitChanges.placeholder')}
            value={modalData.commitDesc}
            name='description'
            onChange={(e) => onChange('desc', e.target.value)}
            // error={descriptionError}
            // status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default FinetuningCommit;
