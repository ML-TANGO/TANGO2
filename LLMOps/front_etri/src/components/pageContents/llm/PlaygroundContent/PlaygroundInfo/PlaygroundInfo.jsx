import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2, Switch, Textarea } from '@tango/ui-react';

import {
  postPlaygroundStartAccel,
  postPlaygroundStopAccel,
  putDescription,
} from '@src/apis/llm/playground';
import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import { STATUS_SUCCESS } from '@src/network';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';

import { calPlusNineHours, copyToClipboardWithToast } from '@src/utils';

import classNames from 'classnames/bind';
import style from './PlaygroundInfo.module.scss';

import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';

const cx = classNames.bind(style);

const handleDesc = (e, dispatch, info) => {
  dispatch(
    handleSetPlaygroundState({
      type: 'info',
      info: {
        ...info,
        description: e.target.value,
      },
    }),
  );
};

const handleModifyDescBtn = async (
  playgroundId,
  description,
  setIsDescription,
) => {
  const { status, message } = await putDescription({
    playgroundId,
    description,
  });
  if (status !== STATUS_SUCCESS) {
    toast.error(message);
  } else {
    setIsDescription((prev) => !prev);
  }
};

const PlaygroundInfo = React.memo(() => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { did: playgroundId } = match.params;

  const {
    id,
    create_datetime,
    description,
    owner,
    name,
    update_datetime,
    access,
    users,
  } = useSelector((state) => state.llmPlayground.info, shallowEqual);
  const { accellator, isAccellator } = useSelector(
    (state) => state.llmPlayground,
    shallowEqual,
  );

  const userJoinText = users.join(', ');

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );

  const { format, method, url } = useSelector(
    (state) => state.llmPlayground.info_request,
    shallowEqual,
  );
  const formatJson = JSON.stringify(format, null, 2);

  const [isDescription, setIsDescription] = useState(false);
  const isDisabled = calIsDeployLoading(statusType);

  const [isLoadingAccel, setIsLoadingAccel] = useState(false);
  const handleAccelator = async () => {
    if (!id) return toast.error(t('playground.header.connecting.message'));
    if (isLoadingAccel) return;

    dispatch(
      handleSetPlaygroundState({
        type: 'accellator',
        accellator: !accellator,
      }),
    );

    if (!accellator) {
      setIsLoadingAccel(true);
      await postPlaygroundStartAccel();
      setIsLoadingAccel(false);
    } else {
      setIsLoadingAccel(true);
      await postPlaygroundStopAccel();
      setIsLoadingAccel(false);
    }
  };

  const handleCopy = useCallback(() => {
    if (!method) {
      toast.error('배포를 활성화해주세요.');
      return;
    }
    copyToClipboardWithToast(url);
  }, [method, url]);

  return (
    <div className={cx('info-wrapper', isDisabled && 'disabled')}>
      <PlaygroundFrame style={{ height: '100%' }}>
        <div className={cx('flex-32')}>
          <h3 className={cx('title')}>{t('information.label')}</h3>
          <div className={cx('edit-cont')}>
            <div className={cx('explain-cont')}>
              <div className={cx('left-cont')}>
                <span className={cx('label')}>
                  {t('template.searchPlaceholderDescription.label')}
                </span>
                {!isDescription && (
                  <button
                    onClick={() => setIsDescription(true)}
                    aria-label='설명 수정 버튼'
                    disabled={isDisabled}
                    className={cx('button')}
                  >
                    <img src={EditIcon} alt='' />
                  </button>
                )}
              </div>
              {isDescription && (
                <ButtonV2
                  label='수정'
                  colorType='skyblue'
                  onClick={() =>
                    handleModifyDescBtn(
                      playgroundId,
                      description,
                      setIsDescription,
                    )
                  }
                />
              )}
            </div>
            <Textarea
              size='large'
              placeholder={t('playground.add.desc.placeholder')}
              value={description}
              name='description'
              onChange={(e) =>
                handleDesc(e, dispatch, {
                  id,
                  create_datetime,
                  description,
                  owner,
                  name,
                  update_datetime,
                  users,
                  access,
                })
              }
              customStyle={{
                fontSize: '14px',
                display: !isDescription && 'none',
              }}
            />
            {!isDescription && (
              <p className={cx('desc-cont')}>
                {description.length === 0 ? '-' : description}
              </p>
            )}
            {isDescription && (
              <span className={cx('desc-length-txt')}>
                {description.length}/1000
              </span>
            )}
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('accessType.label')}</span>
            <div className={cx('flex-row-16')}>
              <span className={cx('label')}>
                {access ? 'Public' : 'Private'}
              </span>
              <p className={cx('value')}>{userJoinText}</p>
            </div>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('owner.label')}</span>
            <span className={cx('value')}>{owner}</span>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}> {t('createdAt.label')}</span>
            <span className={cx('value')}>
              {calPlusNineHours(create_datetime)}
            </span>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('recent.updateAt.label')}</span>
            <span className={cx('value')}>
              {calPlusNineHours(update_datetime)}
            </span>
          </div>
          <div className={cx('border')} />
          <div className={cx('request-url-cont')}>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>Request URL</span>
              <button
                onClick={handleCopy}
                aria-label='URL 복사 버튼'
                disabled={isDisabled}
                className={cx('button')}
              >
                <img
                  className={cx('copy-img')}
                  src='/src/static/images/icon/copy-icon2.svg'
                  alt=''
                />
              </button>
            </div>
            <div
              className={cx('url-paragraph')}
              style={{ textWrap: 'wrap', color: !method && '#c1c1c1' }}
            >
              {method
                ? `[${method}] ${url}`
                : '배포가 활성화되면 Request URL이 생성됩니다.'}
            </div>
            <div className={cx('flex-8')}>
              <span className={cx('label')}>요청 JSON 포맷</span>
              {statusType === 'stop' && (
                <div className={cx('stop-json-cont')}>
                  배포가 활상화되면 JSON 포맷이 생성됩니다.
                </div>
              )}
              {statusType !== 'stop' && (
                <Textarea
                  value={formatJson}
                  customStyle={{ color: '#747474', height: '292px' }}
                />
              )}
            </div>
          </div>
        </div>
      </PlaygroundFrame>
    </div>
  );
});

export default PlaygroundInfo;
