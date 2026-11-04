import { Badge } from '@jonathan/ui-react';

import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

import { convertBinaryByte } from '@src/utils';

import AllStorageStack from '../../AllStorageStack';

import classNames from 'classnames/bind';
import style from './StorageMainList.module.scss';

const cx = classNames.bind(style);

const calBadge = (type, t) => {
  if (type === 'nfs')
    return {
      label: t('network'),
      color: 'primary-2',
    };

  if (type === 'local')
    return {
      label: t('local'),
      color: 'pink',
    };

  return {
    label: t('error'),
    color: 'gray',
  };
};

const StorageMainList = ({ storageDataList, handleMoveStorage }) => {
  const { t } = useTranslation();

  const headerRef = useRef(null);
  const scrollContRef = useRef(null);

  const handleBodyScroll = () => {
    if (headerRef.current && scrollContRef.current) {
      headerRef.current.scrollLeft = scrollContRef.current.scrollLeft;
    }
  };

  useEffect(() => {
    if (scrollContRef.current) {
      scrollContRef.current.addEventListener('scroll', handleBodyScroll);
    }

    return () => {
      if (scrollContRef.current) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        scrollContRef.current.removeEventListener('scroll', handleBodyScroll);
      }
    };
  }, []);

  return (
    <div className={cx('table')}>
      <div ref={scrollContRef} className={cx('scroll-cont')}>
        <div ref={headerRef} className={cx('thead')}>
          <div className={cx('tr')}>
            <div className={cx('td')}>{t('storageServer.label')}</div>
            <div className={cx('td')}>{t('all.amount.label')}</div>
            <div className={cx('td')}>{t('connectionType.label')}</div>
            <div className={cx('td')}>{t('allocate.usage.label')}</div>
          </div>
        </div>
        <div className={cx('tbody')}>
          {storageDataList &&
            storageDataList.length !== 0 &&
            storageDataList.map((info, idx) => {
              const { alloc, used, size: totalSize } = info.usage;
              const { percentage: allocPercent } = calPercent(totalSize, alloc);
              const { percentage: usedPercent } = calPercent(totalSize, used);
              const { label, color } = calBadge(info.fstype, t);

              return (
                <div className={cx('tr')} key={idx}>
                  <div
                    className={cx('td', 'cursor')}
                    onClick={() => handleMoveStorage(info.name)}
                  >
                    {info.name}
                  </div>
                  <div className={cx('td')}>{convertBinaryByte(totalSize)}</div>
                  <div className={cx('td')}>
                    <Badge label={label} type={color} size='l' />
                  </div>
                  <div className={cx('td', 'flex-cont')}>
                    <AllStorageStack
                      label='할당'
                      labelValue={convertBinaryByte(alloc)}
                      totalSize={convertBinaryByte(totalSize)}
                      percentage={allocPercent}
                    />
                    <div className={cx('border')} />
                    <AllStorageStack
                      label='사용'
                      labelValue={convertBinaryByte(used)}
                      totalSize={convertBinaryByte(totalSize)}
                      percentage={usedPercent}
                    />
                  </div>
                </div>
              );
            })}
          {storageDataList.length === 0 && (
            <div className={cx('nodata')}>{t('noData.message')}</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StorageMainList;
