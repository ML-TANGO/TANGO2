import classNames from 'classnames/bind';
import style from './DataCollectCardItem.module.scss';

import IconLock from '@src/static/images/icon/00-ic-info-lock.svg';

const cx = classNames.bind(style);

export const calCollectCycleUnit = (collect_cycle_unit) => {
  if (collect_cycle_unit === 'hour') return '시간';
  if (collect_cycle_unit === 'day') return '일';
  if (collect_cycle_unit === 'month') return '개월';
  if (collect_cycle_unit === 'year') return '년';
  return '';
};

export const calDataType = (dataType) => {
  if (dataType === 'public_api') return '공개 API';
  if (dataType === 'crawling') return '웹 크롤링';
  if (dataType === 'remote_server') return '원격 서버';
  if (dataType === 'flightbase') return 'FLIGHTBASE';
  return '';
};

export default function DataCollectCardItem({
  id,
  info,
  title,
  owner,
  isAccess,
  instanceName,
  instanceCount,
  dataType,
  dataset_name,
  dataset_path,
  collect_cycle,
  collect_cycle_unit,
  collect_storage_limit,
  collect_storage_unit,
  instance_count,
  gpu_name,
  gpu_allocate,
  cpu_allocate,
  ram_allocate,
  isBookMark,
  handleDelete,
  handleEdit,
  handleBookMark,
  handleClickCard,
}) {
  const cycleUnit = calCollectCycleUnit(collect_cycle_unit);
  const returnDataType = calDataType(dataType);

  return (
    <div
      className={cx('card-cont', info.status?.status === 'running' && 'active')}
      onClick={(e) => handleClickCard(e, id, info)}
    >
      <div className={cx('header-cont')}>
        <div className={cx('left-cont')}>
          <img
            src={'/src/static/images/icon/dataset-triple-icon.svg'}
            alt='triple-icon'
          />
          <span className={cx('data-type-txt')}>{returnDataType}</span>
          {!isAccess && <img src={IconLock} alt='lock' />}
        </div>
        <div className={cx('right-cont')}>
          <button
            className={cx('delete-btn')}
            onClick={(e) => handleDelete(e, id, title)}
          >
            <img
              className={cx('img')}
              src={'/src/static/images/icon/00-new-trash.svg'}
              alt='trash-btn'
            />
          </button>
          <button
            className={cx('edit-btn')}
            onClick={(e) => handleEdit(e, id, title, info)}
          >
            <img
              className={cx('img')}
              src={'/src/static/images/icon/00-new-edit.svg'}
              alt='edit-btn'
            />
          </button>
          <button
            className={cx('bookmark-btn')}
            onClick={(e) => handleBookMark(e, id, isBookMark)}
          >
            <img
              className={cx('img')}
              src={
                isBookMark
                  ? '/src/static/images/icon/00-ic-basic-bookmark-o.svg'
                  : '/src/static/images/icon/00-ic-basic-bookmark.svg'
              }
              alt='star-btn'
            />
          </button>
        </div>
      </div>
      <div className={cx('contents-cont')}>
        <div className={cx('owner-cont')}>
          <span className={cx('owner-txt')}>{owner ?? '-'}</span>
          <span className={cx('title-txt')}>{title ?? '-'}</span>
          <span className={cx('instance-txt', !instanceName && 'warn')}>
            {instanceName
              ? `${instanceName} x ${instanceCount}EA`
              : '프로젝트 수정 기능을 통해 인스턴스를 재할당해주세요.'}
          </span>
        </div>
        <div className={cx('ingest-info-cont')}>
          <span className={cx('title-txt')}>수집 정보</span>
          <div className={cx('info-cont')}>
            <div className={cx('row')}>
              <span aria-labelledby='ingest-dataset' className={cx('label')}>
                수집 데이터셋
              </span>
              <span id='ingest-dataset' className={cx('value')}>
                {dataset_name ?? '-'}
              </span>
            </div>
            <div className={cx('row')}>
              <span aria-labelledby='ingest-location' className={cx('label')}>
                수집 위치
              </span>
              <span id='ingest-location' className={cx('value')}>
                {dataset_path ? `/${dataset_path}/` : '-'}
              </span>
            </div>
            <div className={cx('row')}>
              <span aria-labelledby='ingest-period' className={cx('label')}>
                수집 주기
              </span>
              <span id='ingest-period' className={cx('value')}>
                {collect_cycle ? `${collect_cycle} ${cycleUnit}` : '-'}
              </span>
            </div>
            <div className={cx('row')}>
              <span aria-labelledby='ingest-data-limit' className={cx('label')}>
                수집 용량 제한
              </span>
              <span id='ingest-data-limit' className={cx('value')}>
                {collect_storage_limit
                  ? `${collect_storage_limit} ${collect_storage_unit}`
                  : '-'}
              </span>
            </div>
          </div>
        </div>
        <div className={cx('instance-cont')}>
          <span className={cx('title-txt')}>인스턴스 구성</span>
          <div className={cx('info-cont')}>
            {instanceName && (
              <>
                <div className={cx('row')}>
                  <span
                    aria-labelledby='ingest-dataset'
                    className={cx('label')}
                  >
                    vGPU
                  </span>
                  <span id='ingest-dataset' className={cx('value')}>
                    {gpu_name ? `${gpu_name} x ${instance_count} EA` : '-'}
                  </span>
                </div>
                <div className={cx('row')}>
                  <span
                    aria-labelledby='ingest-location'
                    className={cx('label')}
                  >
                    vCPU
                  </span>
                  <span id='ingest-location' className={cx('value')}>
                    {cpu_allocate ? `${cpu_allocate} Cores` : '-'}
                  </span>
                </div>
                <div className={cx('row')}>
                  <span aria-labelledby='ingest-period' className={cx('label')}>
                    RAM
                  </span>
                  <span id='ingest-period' className={cx('value')}>
                    {ram_allocate ? `${ram_allocate} GB` : '-'}
                  </span>
                </div>
              </>
            )}
          </div>
          {!instanceName && (
            <p className={cx('instance-warn-message')}>
              프로젝트 수정 기능을 통해 인스턴스를 재할당해주세요.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
