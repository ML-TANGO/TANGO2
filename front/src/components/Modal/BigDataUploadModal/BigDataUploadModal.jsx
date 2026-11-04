import React, { useEffect, useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  extractPath,
} from '@src/utils';

import ModalFrame from '../ModalFrame';
import GitUploadForm from './GitUploadForm';
import ScpUploadForm from './ScpUploadForm';
import WgetForm from './WgetForm';

import classNames from 'classnames/bind';
import style from './BigDataUploadModal.module.scss';

const cx = classNames.bind(style);

const BigDataUploadModal = ({ type, data }) => {
  const { submit, cancel, datasetName, datasetId, loc } = data;

  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [uploadMethod, setUploadMethod] = useState('scp');
  const [gitCommend, setGitCommand] = useState('clone');
  const [isValidate, setIsValiDate] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');

  const [scpErrorMessage, setScpErrorMessage] = useState('');
  const SCP_ERROR_MESSAGE = {
    path: `${t('folderName.placeholder')}`,
    username: `${t('userID.empty.message')}`,
    password: `${t('password.empty.message')}`,
    ip: `${t('remoteIp.placeholder')}`,
    file_path: `${t('folderName.placeholder')}`,
  };

  const WGET_ERROR_MESSAGE = {
    path: `${t('folderName.placeholder')}`,
    upload_url: `${t('url.placeholder')}`,
  };

  const GIT_ERROR_MESSAGE = {
    url: `${t('gitRepositoryUrl.placeholder')}`,
    id: `${t('id.empty.message')}`,
    password: `${t('password.empty.message')}`,
  };

  const [scpForm, setScpForm] = useState({
    username: '',
    password: '',
    ip: '',
    file_path: '',
  });

  const [scpFormError, setScpFormError] = useState({
    username: '',
    password: '',
    ip: '',
    file_path: '',
  });

  const [wgetForm, setWgetForm] = useState({
    upload_url: '',
  });

  const [wgetFormError, setWgetFormError] = useState({
    upload_url: '',
  });

  const [gitForm, setGitForm] = useState({
    // uploadPath: '',
    url: '',
    disclosure: 'public',
    id: '',
    password: '',
    pullPath: '',
  });

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      // 엔터 키 입력 시 실행할 로직 추가
    }
  };

  const checkInputValue = ({ input = '' }) => {
    const invalidCharacters = /[\/\s!@#$%^&*(),.?":{}|<>]/;
    return invalidCharacters.test(input);
  };

  const handleGitCommand = (value) => {
    setGitCommand(value);
  };

  const handleScpForm = (value, formType) => {
    if (!value) {
      setScpFormError({
        ...scpFormError,
        [formType]: SCP_ERROR_MESSAGE[formType],
      });
    } else {
      setScpFormError({
        ...scpFormError,
        [formType]: '',
      });
    }

    setScpForm({
      ...scpForm,
      [formType]: value,
    });

    if (formType === 'path') {
      //

      if (checkInputValue({ input: value })) {
        setScpErrorMessage('nameRule.message');
      } else {
        setScpErrorMessage('');
      }
    }
  };

  const handleWgetForm = (value, formType) => {
    if (!value) {
      setWgetFormError({
        ...wgetFormError,
        [formType]: WGET_ERROR_MESSAGE[formType],
      });
    } else {
      setWgetFormError({
        ...wgetFormError,
        [formType]: '',
      });
    }

    setWgetForm({
      ...wgetForm,
      [formType]: value,
    });
  };

  const handleGitForm = (value, formType) => {
    setGitForm({
      ...gitForm,
      [formType]: value,
    });
  };

  const handleUploadMethod = (value) => {
    setUploadMethod(value);
  };

  const newSubmit = {
    text: submit.text,
    func: async () => {
      let data =
        uploadMethod === 'scp'
          ? scpForm
          : uploadMethod === 'wget'
          ? wgetForm
          : {};

      if (uploadMethod === 'git') {
        data = {
          path: gitForm.pullPath,
          git_repo_url: gitForm.url,
          git_cmd: gitCommend,
          git_access: gitForm.disclosure,
          git_id: gitForm.id,
          git_access_token: gitForm.password,
        };
      }

      const body = {
        dataset_id: datasetId,
        ...data,
      };

      if (extractPath(loc)) {
        body.path = extractPath(loc);
      }

      const response = await callApi({
        url: `upload/${uploadMethod}`,
        method: 'POST',
        body,
      });

      const { status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        defaultSuccessToastMessage('upload');
        dispatch(closeModal(type));
        return;
      }

      errorToastMessage(error, message);
    },
  };

  useEffect(() => {
    if (uploadMethod === 'scp') {
      setIsValiDate(Object.values(scpForm).every((v) => v.length > 0));
      const scpInput = ['username', 'password', 'ip', 'file_path'];

      for (const val of scpInput) {
        if (!scpForm[val]) {
          setFooterMessage(SCP_ERROR_MESSAGE[val]);
          return;
        }
      }
    }

    if (uploadMethod === 'wget') {
      setIsValiDate(Object.values(wgetForm).every((v) => v.length > 0));
      const wgetInput = ['upload_url'];

      for (const val of wgetInput) {
        if (!wgetForm[val]) {
          setFooterMessage(WGET_ERROR_MESSAGE[val]);
          return;
        }
      }
    }

    if (uploadMethod === 'git') {
      if (gitCommend === 'clone') {
        // url 체크
        const gitUrlInput = ['url'];
        for (const val of gitUrlInput) {
          if (!gitForm[val]) {
            setFooterMessage(GIT_ERROR_MESSAGE[val]);
            setIsValiDate(false);
            return;
          }
        }
      }

      const { disclosure } = gitForm;

      if (disclosure === 'private') {
        const gitUrlInput = ['id', 'password'];
        for (const val of gitUrlInput) {
          if (!gitForm[val]) {
            setFooterMessage(GIT_ERROR_MESSAGE[val]);
            setIsValiDate(false);
            return;
          }
        }
      }
      setIsValiDate(true);
    }

    setFooterMessage('');
  }, [scpForm, wgetForm, uploadMethod, gitForm, gitCommend]);

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      title={t('bigDataUpload.label')}
      validate={isValidate}
      footerMessage={footerMessage}
    >
      <h2 className={cx('title')}>{t('bigDataUpload.label')}</h2>
      <div className={cx('form')} onKeyPress={handleKeyPress}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('datasetUploadMethod.label')}
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              name='upload'
              options={[
                { label: 'scp', value: 'scp' },
                { label: 'wget', value: 'wget' },
                { label: 'git', value: 'git' },
              ]}
              value={uploadMethod}
              onChange={(e) => handleUploadMethod(e.target.value)}
              isTranLabel={false}
            />
          </InputBoxWithLabel>
        </div>
        {uploadMethod === 'scp' && (
          <ScpUploadForm
            scpForm={scpForm}
            handleScpForm={handleScpForm}
            datasetName={datasetName}
            scpFormError={scpFormError}
            scpErrorMessage={scpErrorMessage}
            loc={loc}
          />
        )}
        {uploadMethod === 'wget' && (
          <WgetForm
            wgetForm={wgetForm}
            handleWgetForm={handleWgetForm}
            datasetName={datasetName}
            wgetFormError={wgetFormError}
            loc={loc}
          />
        )}
        {uploadMethod === 'git' && (
          <GitUploadForm
            gitForm={gitForm}
            handleGitForm={handleGitForm}
            datasetName={datasetName}
            handleGitCommand={handleGitCommand}
            gitCommend={gitCommend}
          />
        )}
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(BigDataUploadModal);
