import { Textarea } from '@tango/ui-react';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { encrypt } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './HuggingFaceTokenModal.module.scss';

const cx = classNames.bind(style);

const HuggingFaceTokenModal = ({ data, type }) => {
  const { onSubmit, apiUrl } = data;

  const [value, setValue] = useState('');
  const [footerMessage, setFooterMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const { t } = useTranslation();

  const textareaHandler = (e) => {
    const { value } = e.target;

    setValue(value); //
  };

  const checkToken = async () => {
    if (value) {
      setLoading(true);
      const response = await callApi({
        url: apiUrl ? apiUrl : 'models/option/huggingface-token-check',
        method: 'post',
        body: JSON.stringify(encrypt(value)),
      });
      const { status, result, message, error } = response;

      if (status === STATUS_SUCCESS) {
        if (result) {
          // await postHuggingFace({ token: value });
          return result;
        } else {
          setFooterMessage('토큰 다시 확인');
          return result;
        }
      }
    }
  };

  return (
    <NewStyleModalFrame
      title={t('huggingFaceTokenAuthentication.label')}
      type={type}
      submit={{
        text: t('confirm.label'),
        func: async () => {
          const tokenRes = await checkToken();
          setLoading(false);
          if (tokenRes) {
            onSubmit(encrypt(value));
          }
          //
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      isLoading={loading}
      validate={value !== ''}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('huggingFace.input.token.label')}
          labelSize='large'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('huggingFace.input.token.placeholder')}
            value={value}
            name='description'
            onChange={textareaHandler}
            // error={descriptionError}
            // status={descriptionError ? 'error' : 'default'}
            customStyle={{ fontSize: '14px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
        <div className={cx('example')}>
          <div className={cx('label')}>{t('huggingFace.example.label')}</div>
          <div className={cx('value')}>
            hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
          </div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default HuggingFaceTokenModal;
