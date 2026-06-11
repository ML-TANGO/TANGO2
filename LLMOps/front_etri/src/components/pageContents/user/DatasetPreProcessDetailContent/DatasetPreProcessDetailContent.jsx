import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import { ButtonV2 } from '@tango/ui-react';

import { openModal } from '@src/store/modules/modal';

import DevToolPage from './DevToolPage';
import InfoDetail from './InfoDetail';
import ProcessToolPage from './ProcessToolPage';
import usePreprocessSse from './usePreprocessSse';

import classNames from 'classnames/bind';
import style from './DatasetPreProcessDetailContent.module.scss';

const cx = classNames.bind(style);

/**
 * @typedef {'info' | 'devTool' | 'processTool'} TabType
 */

/**
 * @typedef {Object} TabBoxItem
 * @property {string} label
 * @property {TabType} value
 */

/**
 * @typedef {'built-in' | 'advanced'} ProcessType
 */

const DatasetPreProcessDetailContent = () => {
  const { t } = useTranslation();
  const history = useHistory();
  const { did, id: wid } = useParams();

  const dispatch = useDispatch();

  /** @type {[TabType, React.Dispatch<React.SetStateAction<TabType>>]} */
  const [tab, setTab] = useState(/** @type {TabType} */ ('info'));

  /** @type {[type: ProcessType, setType: React.Dispatch<React.SetStateAction<ProcessType>>]} */
  const [type, setType] = useState('');

  const [processName, setProcessName] = useState('');
  const [builtInDataType, setBuiltInDataType] = useState('');
  const { data } = usePreprocessSse({ did });

  /**
   * @type {TabBoxItem[]}
   */
  const tabBox = [
    { label: t('information.label'), value: 'info' },
    { label: t('developTool.label'), value: 'devTool' },
    {
      label: `${t('preprocess.label')} ${t(
        'deploymentTypeTraining.tool.label',
      )}`,
      value: 'processTool',
    },
  ];

  const goToBack = () => {
    history.goBack();
  };

  const openJobCreateModal = () => {
    dispatch(
      openModal({
        modalType:
          type === 'advanced'
            ? 'DATASET_JOB_CREATE'
            : 'DATASET_BUILT_IN_JOB_CREATE',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {},
          },
          cancel: {
            text: 'cancel.label',
          },
          preprocessing_id: did,
          workspaceId: wid,
        },
      }),
    );
  };

  const openGuideModal = () => {
    dispatch(
      openModal({
        modalType: 'PREPROCESS_GUIDE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {},
          },
          builtInDataType,
        },
      }),
    );
  };

  return (
    <div className={cx('container')}>
      <div className={cx('back-btn')} onClick={goToBack}>
        <img
          height={16}
          width={16}
          src='/images/icon/00-ic-basic-arrow-02-left.svg'
          alt=''
        />
        <span className={cx('text')}>
          {`${t('data.label')} ${t('preprocess.label')}`}
        </span>
      </div>
      <div className={cx('process-name')}>
        <span>{processName}</span>
        <div className={cx('left-side')}>
          {data.status === 'running' && (
            <span className={cx('warning')}>
              현재 개발 도구가 실행 중입니다.
            </span>
          )}

          {tab === 'processTool' && type === 'built-in' && (
            <div className={cx('guide-btn')} onClick={openGuideModal}>
              전처리기 사용 가이드
            </div>
          )}

          {tab === 'processTool' && (
            <ButtonV2
              size='l'
              label={`JOB ${t('create.label')}`}
              onClick={openJobCreateModal}
            />
          )}
        </div>
      </div>
      <div className={cx('tab-box')}>
        {tabBox.map(({ label, value }) => (
          <div
            key={label}
            className={cx(
              'tab',
              tab === value && 'selected',
              value === 'devTool' && type !== 'advanced' && 'hide',
            )}
            onClick={() => setTab(value)}
          >
            {label}
          </div>
        ))}
      </div>

      {tab === 'info' && (
        <InfoDetail
          did={did}
          status={data.status === 'running'}
          setProcessName={setProcessName}
          setType={setType}
        />
      )}
      {tab === 'devTool' && <DevToolPage did={did} wid={wid} />}
      {tab === 'processTool' && (
        <ProcessToolPage
          openJobCreateModal={openJobCreateModal}
          wid={wid}
          did={did}
          processType={type}
          setBuiltInDataType={setBuiltInDataType}
        />
      )}
    </div>
  );
};

export default DatasetPreProcessDetailContent;
