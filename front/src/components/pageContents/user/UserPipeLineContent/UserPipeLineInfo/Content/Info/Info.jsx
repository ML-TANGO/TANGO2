import React from 'react';
import { useTranslation } from 'react-i18next';

import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';

import { calPlusNineHours } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from '../../UserPipeLineInfo.module.scss';

const cx = classNames.bind(style);

export default function Info({ ...pipelineInfo }) {
  const {
    create_datetime,
    description,
    owner_name,
    access,
    update_datetime,
    type,
    built_in_specification: specification, // 명세서
    built_in_type: builtInType, // 헬스케어, 제조
    built_in_sub_type: builtInSubType,
    built_in_data_type: dataType, // 데이터 유형
    built_in_preprocessing_list: preprocessingList, // 전처리 리스트
  } = pipelineInfo;

  const { t } = useTranslation();

  return (
    <PlaygroundFrame>
      <div className={cx('row')}>
        {type === 'advanced' && (
          <>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>{t('description.label')}</span>
              <p className={cx('value')}>
                {!description.length ? '-' : description}
              </p>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>{t('pipeline.type.title')}</span>
              <span className={cx('value')}>{'Custom 파이프라인 생성'}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>접근 권한</span>
              <span className={cx('value')}>
                {access ? 'Public' : 'Private'}
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>소유자</span>
              <span className={cx('value')}>{owner_name ?? '-'}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>생성 일시</span>
              <span className={cx('value')}>
                {calPlusNineHours(create_datetime) ?? '0000-00-00 00:00:00'}
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>최근 업데이트 일시</span>
              <span className={cx('value')}>
                {calPlusNineHours(update_datetime) ?? '0000-00-00 00:00:00'}
              </span>
            </div>
          </>
        )}
        {type === 'built-in' && (
          <>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>{t('description.label')}</span>
              <p className={cx('value')}>
                {!description.length ? '-' : description}
              </p>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>
                {t('pipeline.training_data.specification')}
              </span>
              <span className={cx('value')}>{specification}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>{t('pipeline.type.title')}</span>
              <span className={cx('value')}>{'Built-in 파이프라인 사용'}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>적용 분야</span>
              <span className={cx('value')}>
                <span style={{ marginRight: '16px', color: '#747474' }}>
                  {builtInType}
                </span>
                <span>{builtInSubType}</span>
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>{t('dataType.label')}</span>
              <span className={cx('value')}>{dataType}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>
                {t('pipeline.data.preprocess.label')}
              </span>
              <span className={cx('value')}>
                {preprocessingList?.map((v, i) => {
                  return (
                    <span className={cx('preprocessing-list')}>
                      <span style={{ marginRight: '4px', color: '#747474' }}>
                        {i + 1}
                      </span>
                      <span>{v}</span>
                    </span>
                  );
                })}
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>접근 권한</span>
              <span className={cx('value')}>
                {access ? 'Public' : 'Private'}
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>소유자</span>
              <span className={cx('value')}>{owner_name ?? '-'}</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>생성 일시</span>
              <span className={cx('value')}>
                {calPlusNineHours(create_datetime) ?? '0000-00-00 00:00:00'}
              </span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label')}>최근 업데이트 일시</span>
              <span className={cx('value')}>
                {calPlusNineHours(update_datetime) ?? '0000-00-00 00:00:00'}
              </span>
            </div>
          </>
        )}
      </div>
    </PlaygroundFrame>
  );
}
