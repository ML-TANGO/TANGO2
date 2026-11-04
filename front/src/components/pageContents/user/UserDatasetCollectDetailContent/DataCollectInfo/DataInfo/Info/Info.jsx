import React from 'react';
import { useTranslation } from 'react-i18next';

import dayjs from 'dayjs';

import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';
import { calCollectCycleUnit } from '@src/components/pageContents/user/UserDatasetCollectMenuContent/DataCollectCardItem/DataCollectCardItem';

import { calPlusNineHours } from '@src/utils';

import classNames from 'classnames/bind';
import style from './Info.module.scss';

const cx = classNames.bind(style);

export default function Info({
  description,
  dataset_name,
  dataset_path,
  collect_cycle,
  collect_cycle_unit,
  collect_storage_limit,
  collect_storage_unit,
  access,
  owner,
  members,
  create_datetime,
  start_datetime,
}) {
  const { t } = useTranslation();

  const collectCycleUnit = calCollectCycleUnit(collect_cycle_unit);
  const memberString = members.join(', ');

  return (
    <PlaygroundFrame style={{ height: 'fit-content' }}>
      <div className={cx('flex-32')}>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>
            {t('template.searchPlaceholderDescription.label')}
          </span>
          <p className={cx('value', 'desc')}>
            {!description ? '-' : description}
          </p>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('collect.location.label')}</span>
          <div className={cx('flex-row-8')}>
            <img
              className={cx('dataset-icon')}
              src='/src/static/images/icon/dataset-black.svg'
              alt='dataset-icon'
            />
            <span className={cx('value')}>{dataset_name}</span>
          </div>
          <div className={cx('flex-row-8')}>
            <img
              className={cx('dataset-icon')}
              src='/src/static/images/icon/folder-black.svg'
              alt='folder-icon'
            />
            <span className={cx('value')}>/{dataset_path}/</span>
          </div>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>수집 주기</span>
          <span className={cx('value')}>
            {collect_cycle} {collectCycleUnit}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>수집 용량 제한</span>
          <span className={cx('value')}>
            {collect_storage_unit
              ? `${collect_storage_limit} ${collectCycleUnit}`
              : '-'}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>접근 권한</span>
          <div className={cx('flex-row-8')}>
            <span className={cx('label')}>
              {!access ? 'Private' : 'Public'}
            </span>
            <span className={cx('value')}>{memberString}</span>
          </div>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>소유자</span>
          <span className={cx('value')}>{owner}</span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>생성 일시</span>
          <span className={cx('value')}>
            {calPlusNineHours(create_datetime)}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>최근 수집 실행 일시</span>
          <span className={cx('value')}>
            {start_datetime ? calPlusNineHours(start_datetime) : '-'}
          </span>
        </div>
      </div>
    </PlaygroundFrame>
  );
}
