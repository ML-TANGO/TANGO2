// External training launch modal — mirrors the FINETUNING_SETTING modal
// frame so the operator UX feels identical, but the body is much lighter:
// a partner container only needs (manifest, namespace, params).
//
// Flow:
//   1. user clicks "학습 시작" on the FineTuning tab of an external model
//   2. parent dispatches openModal('EXTERNAL_TRAINING_START', {..., onSubmit})
//   3. this modal validates params JSON + namespace
//   4. onSubmit(payload) returns true/false from the parent (which does the
//      actual POST /external/jobs + PATCH /models/{id}/external-job)
//   5. if true → modal closes + parent refreshes

import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './ExternalTrainingStartModal.module.scss';

const cx = classNames.bind(style);

const ExternalTrainingStartModal = ({ data, type }) => {
  const {
    manifestName,
    manifestVersion,
    onSubmit, // parent's POST + PATCH handler
    refresh,
  } = data || {};
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [namespaceInput, setNamespaceInput] = useState('tango-system');
  const [paramsInput, setParamsInput] = useState('{}');
  const [submitting, setSubmitting] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');

  // Pre-fill default params from the manifest detail endpoint.
  useEffect(() => {
    if (!manifestName) return;
    let cancelled = false;
    const fetchDefaults = async () => {
      const response = await callApi({
        url: `external/manifests/${encodeURIComponent(manifestName)}`,
        method: 'get',
      });
      if (cancelled) return;
      const { status, result } = response;
      if (
        status === STATUS_SUCCESS &&
        result &&
        Array.isArray(result.versions)
      ) {
        const match = result.versions.find(
          (v) => v.manifest_version === manifestVersion,
        );
        if (
          match &&
          match.default_params &&
          typeof match.default_params === 'object'
        ) {
          try {
            setParamsInput(JSON.stringify(match.default_params, null, 2));
          } catch (_) {
            /* keep current */
          }
        }
      }
    };
    fetchDefaults();
    return () => {
      cancelled = true;
    };
  }, [manifestName, manifestVersion]);

  const validate = useCallback(() => {
    if (!namespaceInput.trim()) {
      return t('externalTraining.start.failed.label');
    }
    try {
      const parsed = JSON.parse(paramsInput);
      if (
        parsed === null ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed)
      ) {
        return t('externalTraining.start.invalidJson.label');
      }
    } catch (_) {
      return t('externalTraining.start.invalidJson.label');
    }
    return '';
  }, [namespaceInput, paramsInput, t]);

  const handleSubmit = useCallback(async () => {
    const msg = validate();
    if (msg) {
      setFooterMessage(msg);
      return;
    }
    setSubmitting(true);
    let parsedParams;
    try {
      parsedParams = JSON.parse(paramsInput);
    } catch (_) {
      errorToastMessage(null, t('externalTraining.start.invalidJson.label'));
      setSubmitting(false);
      return;
    }
    let ok = false;
    if (typeof onSubmit === 'function') {
      ok = await onSubmit({
        namespace: namespaceInput.trim(),
        params: parsedParams,
      });
    }
    setSubmitting(false);
    if (ok) {
      if (typeof refresh === 'function') refresh();
      dispatch(closeModal('EXTERNAL_TRAINING_START'));
    }
  }, [
    validate,
    paramsInput,
    namespaceInput,
    onSubmit,
    refresh,
    dispatch,
    t,
  ]);

  const footerText = footerMessage || (submitting ? t('externalTraining.start.submitting.label') : '');

  return (
    <NewStyleModalFrame
      title={t('externalTraining.model.startTraining.label')}
      type={type}
      submit={{
        text: t('externalTraining.model.startTraining.label'),
        func: handleSubmit,
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!submitting && validate() === ''}
      isResize={true}
      isMinimize={true}
      isLoading={submitting}
      footerMessage={footerText}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('externalTraining.model.manifest.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            value={`${manifestName ?? ''}@${manifestVersion ?? ''}`}
            isReadOnly
            disableLeftIcon
            disableClearBtn
            customStyle={{ fontSize: '14px' }}
          />
        </InputBoxWithLabel>
      </div>

      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('externalTraining.start.namespace.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            value={namespaceInput}
            onChange={(e) => setNamespaceInput(e.target.value)}
            disableLeftIcon
            disableClearBtn
            customStyle={{ fontSize: '14px' }}
          />
        </InputBoxWithLabel>
      </div>

      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('externalTraining.start.params.label')}
          labelSize='large'
          disableErrorMsg
        >
          <textarea
            className={cx('params-textarea')}
            value={paramsInput}
            onChange={(e) => setParamsInput(e.target.value)}
            spellCheck={false}
          />
          <div className={cx('hint')}>
            {t('externalTraining.start.params.hint')}
          </div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default ExternalTrainingStartModal;
