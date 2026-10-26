import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { ButtonV2, Textarea } from '@tango/ui-react';

import { handleSetModelState } from '@src/store/modules/llmModel';
// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import SimpleNav from '../SimpleNav';

import { addNineHours, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ModelInfo.module.scss';

import EditIcon from '@images/icon/00-ic-basic-pen.svg';
import GroupIcon from '@images/icon/00-ic-llm-group.svg';
import IconSmile from '@images/icon/ic-smile.png';

const cx = classNames.bind(style);

const ModelInfo = memo(function ModelInfo({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const [modelInfo, setModelInfo] = useState(null);
  const isLoading = useRef(false);
  const dispatch = useDispatch();
  const [infoData, setInfoData] = useState(null);
  const [isDescription, setIsDescription] = useState(false);
  const [description, setDescription] = useState(null);

  const { modelId } = data;

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // get Info list
  const getInfoData = useCallback(async () => {
    const response = await callApi({
      url: `models/fine-tuning/summary?model_id=${modelId}`,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setInfoData(result);
      setDescription(result.description);
      dispatch(
        handleSetModelState({
          type: 'info',
          info: {
            name: result.name,
          },
        }),
      );
    } else {
      errorToastMessage(error, message);
    }
  }, [dispatch, modelId]);

  // ** 수정 버튼 핸들러 **
  const onClickEdit = async () => {
    const response = await callApi({
      url: 'models/detail',
      method: 'put',
      body: {
        model_id: modelId,
        description: description ?? '',
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setIsDescription(false);
      getInfoData();
    } else {
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    getInfoData();
  }, [getInfoData]);

  return (
    <div id='info-tab' className={cx('info-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        titleName={infoData?.name ?? ''}
      />
      <div className={cx('container')}>
        <div className={cx('label')}>
          <div className={cx('desc-title')}>
            {t('description.label')}
            {!isDescription && (
              <img
                src={EditIcon}
                alt=''
                onClick={() => setIsDescription(true)}
              />
            )}
          </div>
          {isDescription && (
            <ButtonV2
              label={t('update.label')}
              colorType='skyblue'
              onClick={() => onClickEdit()}
            />
          )}
        </div>
        <Textarea
          size='large'
          placeholder={t('playground.add.desc.placeholder')}
          value={description}
          name='description'
          onChange={(e) => setDescription(e.target.value)}
          maxLength={'1000'}
          customStyle={{
            fontSize: '14px',
            display: !isDescription && 'none',
            height: '80px',
          }}
        />
        {isDescription && (
          <div className={cx('text-length')}>{description?.length}/1000</div>
        )}
        <div className={cx('value')}>
          {infoData?.description ? (
            <span
              style={{
                display: isDescription && 'none',
              }}
            >
              {infoData.description}
            </span>
          ) : (
            <span className={cx('no-desc')}>{t('no.desc')}</span>
          )}
        </div>
        <div className={cx('label')}>{t('model.label')}</div>

        <div className={cx('value')}>
          {infoData?.load_type === 'multimodal' ? (
            <div className={cx('multimodal-box')}>
              <div className={cx('header-row')}>
                <img src={IconSmile} alt='icon' />
                <span className={cx('model')}>Multimodal</span>
              </div>
              <div className={cx('model-list')}>
                {infoData?.huggingface_model_id?.split(',').map((model, idx) => (
                  <span key={idx}>Model {idx + 1}: {model.trim()}</span>
                ))}
              </div>
            </div>
          ) : infoData?.commit_model_name ? (
            <div className={cx('model-box')}>
              <img src={GroupIcon} alt='icon' />
              <span className={cx('model')}>GenAI Platform</span>
              <span>{infoData?.commit_model_name}</span>
            </div>
          ) : (
            <div className={cx('model-box')}>
              <img src={IconSmile} alt='icon' />
              <span className={cx('model')}>Hugging Face</span>
              <span>{infoData?.huggingface_model_id}</span>
            </div>
          )}
        </div>
        <div className={cx('label')}>{t('creator.label')}</div>
        <div className={cx('value')}>{infoData?.create_user_name ?? '-'}</div>
        <div className={cx('label')}>{t('createdAt.label')}</div>
        <div className={cx('value')}>
          {infoData?.create_datetime
            ? addNineHours(infoData?.create_datetime)
            : '-'}
        </div>
        <div className={cx('label')}>{t('lastUpdatedTime.label')}</div>
        <div className={cx('value')}>
          {infoData?.update_datetime
            ? addNineHours(infoData?.update_datetime)
            : '-'}
        </div>
      </div>
    </div>
  );
});

export default ModelInfo;
