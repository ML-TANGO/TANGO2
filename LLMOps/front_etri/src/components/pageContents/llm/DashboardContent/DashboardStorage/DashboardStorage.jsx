import React from 'react';
import { useTranslation } from 'react-i18next';

import CircleGauge from '@src/components/molecules/CircleGauge';
import Stack from '@src/components/pageContents/admin/AdminNodeContent/nodeComponent/NodeRateList/Stack';

import DashboardFrame from '../DashboardFrame';
import ListDonut from './ListDonut/ListDonut';

import { convertBinaryByte } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardStorage.module.scss';

const cx = classNames.bind(style);

const StackList = ({ list, zeromessage }) => {
  if (list === null)
    return (
      <div className={cx('error')}>
        <span>서버로부터 응답이 없습니다.</span>
      </div>
    );
  if (list.length === 0)
    return (
      <div className={cx('error')}>
        <span>{zeromessage}</span>
      </div>
    );

  return (
    <div className={cx('content-list')}>
      {list.map((info, idx) => {
        return <StackItem key={idx} name={info.name} usage={info.usage} />;
      })}
    </div>
  );
};

const StackItem = React.memo(({ name, usage }) => {
  return (
    <div className={cx('content-item-cont')}>
      <span className={cx('item-title')}>{name}</span>
      <div className={cx('item-bar-cont')}>
        <Stack isRateLabel={false} rate={usage} />
        <span className={cx('percent')}>{usage} %</span>
      </div>
    </div>
  );
});

export default function DashboardStorage({
  type = 'fb',
  title,
  mainStorage,
  dataStorage,
}) {
  const { t } = useTranslation();

  const {
    total: mainTotal,
    avail: mainAvail,
    usage: mainUsage,
    used: mainUsed,
    allm_list: mainProjectList,
    project_list: fbProjectList,
    allm_usage: mainAllmUsage,
    fb_usage: mainFbUsage,
  } = mainStorage;
  const stackList = type === 'fb' ? fbProjectList : mainProjectList;

  const {
    total: dataTotal,
    avail: dataAvail,
    usage: dataUsage,
    used: dataUsed,
    dataset_list: dataProjectList,
  } = dataStorage;

  const mainfbsize = convertBinaryByte((mainTotal * mainFbUsage) / 100);
  const mainLLMsize = convertBinaryByte((mainTotal * mainAllmUsage) / 100);

  const mainDonutList = [
    {
      value: mainFbUsage,
      color: type === 'fb' ? '#2D76F8' : '#DBDBDB',
      name: 'FLIGHTBASE',
      size: mainfbsize,
    },
    {
      value: mainAllmUsage,
      color: type === 'fb' ? '#DBDBDB' : '#2D76F8',
      name: 'GenAI Platform',
      size: mainLLMsize,
    },
    { value: 100 - mainFbUsage - mainAllmUsage, color: '#F0F0F0', name: '' },
  ];

  return (
    <DashboardFrame
      title={title}
      style={{ height: '560px' }}
      contentStyle={{ padding: '0px', height: '100%' }}
    >
      <div className={cx('grid-column')}>
        <div className={cx('storage-cont')}>
          <div className={cx('graph-cont')}>
            <div className={cx('graph')}>
              <ListDonut
                data={mainDonutList}
                storageType='Main'
                width={160}
                percentage={mainUsage}
              />
            </div>
            <ul className={cx('label-list')}>
              <li className={cx('label-item')}>
                <span className={cx('label')}>
                  {t('storageAllocationSize.label')}
                </span>
                <span className={cx('value')}>
                  {convertBinaryByte(mainTotal)}
                </span>
              </li>
              <li className={cx('label-item')}>
                <span className={cx('label')}>{t('used.label')}</span>
                <span className={cx('value')}>
                  {convertBinaryByte(mainUsed)}
                </span>
              </li>
              <li className={cx('label-item')}>
                <span className={cx('label')}>
                  {t('storageAvailable.label')}
                </span>
                <span className={cx('value')}>
                  {convertBinaryByte(mainAvail)}
                </span>
              </li>
            </ul>
          </div>
          <div className={cx('bar-cont')}>
            <p className={cx('bar-label')}>{t('mainStorageUsage.label')}</p>
            <StackList
              list={stackList}
              zeromessage={t('nodataMainStorageProject')}
            />
          </div>
        </div>
        <div className={cx('storage-cont')}>
          <div className={cx('graph-cont')}>
            <div className={cx('graph')}>
              <CircleGauge percentage={dataUsage}>
                <div className={cx('circle-cont')}>
                  <span className={cx('label')}>Data</span>
                  <span className={cx('percent')}>
                    {dataUsage === '-' ? '-' : `${dataUsage} %`}
                  </span>
                </div>
              </CircleGauge>
            </div>
            <ul className={cx('label-list')}>
              <li className={cx('label-item')}>
                <span className={cx('label')}>{t('allocateGpu.label')}</span>
                <span className={cx('value')}>
                  {convertBinaryByte(dataTotal)}
                </span>
              </li>
              <li className={cx('label-item')}>
                <span className={cx('label')}>{t('used.label')}</span>
                <span className={cx('value')}>
                  {convertBinaryByte(dataUsed)}
                </span>
              </li>
              <li className={cx('label-item')}>
                <span className={cx('label')}>
                  {t('storageAvailable.label')}
                </span>
                <span className={cx('value')}>
                  {convertBinaryByte(dataAvail)}
                </span>
              </li>
            </ul>
          </div>
          <div className={cx('bar-cont')}>
            <p className={cx('bar-label')}>{t('dataStorageUsage.label')}</p>
            <StackList
              list={dataProjectList}
              zeromessage={t('nodataDataStorageProject')}
            />
          </div>
        </div>
      </div>
    </DashboardFrame>
  );
}
