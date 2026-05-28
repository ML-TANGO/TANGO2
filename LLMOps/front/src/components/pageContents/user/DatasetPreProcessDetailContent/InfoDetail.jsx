import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getKoreaTime } from '@src/datetimeUtils';

import ProcessToolTip from '@src/components/Modal/AddDatasetPreprocess/ProcessToolTip';

import { callApi, STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './InfoDetail.module.scss';

import info from '@src/static/images/icon/00-ic-gray-info.svg';

const cx = classNames.bind(style);

const INSTANCE_KEY = {
  project: '학습',
  deployment: '배포',
  preprocessing: '전처리기',
  collect: '수집기',
  analyzer: '분석기',
  fine_tuning: '모델',
};

const InfoDetail = ({ did, setProcessName, status, setType }) => {
  const { t } = useTranslation();
  const [processInfo, setProcessInfo] = useState({
    description: '',
    access: 'Public',
    owner: '',
    createAt: '',
    updateAt: '',
    instance: '',
    instanceName: '',
    gpu: '',
    cpu: '',
    ram: '',
    instanceType: '',
    users: [],
    type: '',
    dataTf: '',
    dataType: '',
    gpuCondition: true,
    cpuCondition: true,
    ramCondition: true,
    instanceUsed: [],
  });

  const fetchDetailInfo = async () => {
    const response = await callApi({
      url: `preprocessing/${did}`,
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      const {
        name,
        description,
        access,
        owner_name,
        create_datetime,
        update_datetime,
        instance_info,
        private_user_list,
        type,
        built_in_data_tf,
        built_in_data_type,
      } = result;

      const {
        instance_name,
        instance_allocate,
        gpu_allocate,
        cpu_allocate,
        ram_allocate,
        instance_type,
        cpu_available,
        gpu_available,
        ram_available,
        instance_used,
      } = instance_info;

      const instanceUsedList = Object.entries(instance_used).flatMap(
        ([type, items]) => items.map((item) => ({ ...item, type })),
      );

      setProcessName(name);
      setProcessInfo({
        name,
        description,
        access: access === 1 ? 'Public' : 'Private',
        owner: owner_name,
        createAt: create_datetime,
        updateAt: update_datetime,
        instanceName: instance_name,
        instance: instance_allocate,
        gpu: gpu_allocate,
        ram: ram_allocate,
        cpu: cpu_allocate,
        instanceType: instance_type,
        users: private_user_list.map(({ user_name }) => user_name),
        type,
        dataTf: built_in_data_tf,
        dataType: built_in_data_type,
        gpuCondition: gpu_available,
        cpuCondition: cpu_available,
        ramCondition: ram_available,
        instanceUsed: instanceUsedList,
      });
      setType(type);
    }
  };

  useEffect(() => {
    fetchDetailInfo();
  }, []);

  return (
    <div className={cx('container')}>
      <div className={cx('info-container', status && 'running')}>
        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('description.label')}</div>
          <div className={cx('value')}>
            {processInfo.description ? processInfo.description : '-'}
          </div>
        </div>
        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('preprocess.option.label')}</div>
          <div className={cx('value')}>
            {processInfo.type === 'advanced' ? 'Custom' : 'Built-in'} 전처리기
          </div>
        </div>
        {processInfo.type === 'built-in' && (
          <div className={cx('info-box')}>
            <div className={cx('type')}>{t('dataType.label')}</div>
            <div className={cx('value')}>{processInfo.dataType}</div>
          </div>
        )}
        {processInfo.type === 'built-in' && (
          <div className={cx('info-box')}>
            <div className={cx('type')}>{t('conversion.function.label')}</div>
            <div className={cx('value')}>
              {processInfo.dataTf ? processInfo.dataTf : '없음'}
            </div>
          </div>
        )}

        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('accessType.label')}</div>
          <div className={cx('value')}>
            <span
              className={cx(processInfo.access === 'Private' && 'gray-text')}
            >
              {processInfo.access}
            </span>
            <span>{processInfo.users.join(', ')}</span>
          </div>
        </div>
        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('owner.label')}</div>
          <div className={cx('value')}>{processInfo.owner}</div>
        </div>
        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('createdDatetime.label')}</div>
          <div className={cx('value')}>
            {getKoreaTime(processInfo.createAt)}
          </div>
        </div>
        <div className={cx('info-box')}>
          <div className={cx('type')}>{t('lastUpdatedTime.label')}</div>
          <div className={cx('value')}>
            {getKoreaTime(processInfo.updateAt)}
          </div>
        </div>
      </div>
      <div className={cx('option', status && 'running')}>
        <div className={cx('title')}>
          <span>{t('instanceSetting.label')}</span>
          <span
            className={cx(
              'condition-text',
              processInfo.gpuCondition &&
                processInfo.cpuCondition &&
                processInfo.ramCondition &&
                'enough',
            )}
          >
            {processInfo.gpuCondition &&
            processInfo.cpuCondition &&
            processInfo.ramCondition
              ? '즉시 사용 가능'
              : '대기 후 사용 가능'}
          </span>
        </div>
        <div className={cx('instance')}>
          <div className={cx('name')}>
            <span>{t('instance.label')}</span>
            <span>{processInfo.instanceName}</span>
          </div>
          <div className={cx('info')}>
            {processInfo.instance ? (
              <>
                <span>{processInfo.instance}</span>
                <span>EA</span>
              </>
            ) : (
              <span>-</span>
            )}
          </div>
        </div>
        <div className={cx('resource')}>
          {processInfo.type === 'advanced' && (
            <div className={cx('detail')}>
              <span className={cx('type')}>
                <div
                  className={cx(
                    'condition',
                    processInfo.gpuCondition && 'enough',
                  )}
                >
                  {processInfo.gpuCondition ? '여유' : '부족'}
                </div>
                <span>vGPU</span>
                {!processInfo.gpuCondition && (
                  <span>할당 {processInfo.gpu} EA</span>
                )}

                {!processInfo.gpuCondition && (
                  <ProcessToolTip
                    icon={info}
                    position={'up'}
                    iconStyle={{ transform: 'translateY(2px)' }}
                    customStyle={{
                      height: '200px',
                      width: '300px',
                      padding: '24px',
                      transform: 'translate(-120px, -20px)',
                    }}
                    contents={
                      <div className={cx('tool-tip-content')}>
                        <div className={cx('header')}>vGPU 사용 현황</div>
                        {processInfo.instanceUsed.map(
                          ({ name, resources, type }, index) => (
                            <div key={index} className={cx('used-box')}>
                              <span className={cx('deploy-type', type)}>
                                {INSTANCE_KEY[type]}
                              </span>
                              <div className={cx('info')}>
                                <span>{name}</span>
                                <span className={cx('resource')}>
                                  {resources.gpu} EA
                                </span>
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    }
                  />
                )}
              </span>
              <div className={cx('info')}>
                {processInfo.gpu ? (
                  <>
                    <span>{processInfo.gpu}</span>
                    <span>EA</span>
                  </>
                ) : (
                  <span>-</span>
                )}
              </div>
            </div>
          )}

          <div className={cx('detail')}>
            <span className={cx('type')}>
              <div
                className={cx(
                  'condition',
                  processInfo.cpuCondition && 'enough',
                )}
              >
                {processInfo.cpuCondition ? '여유' : '부족'}
              </div>
              <span>vCPU</span>
              {!processInfo.cpuCondition && (
                <ProcessToolTip
                  icon={info}
                  position={'up'}
                  iconStyle={{ transform: 'translateY(2px)' }}
                  customStyle={{
                    height: '200px',
                    width: '300px',
                    padding: '24px',
                    transform: 'translate(20px, -10px)',
                  }}
                  contents={
                    <div className={cx('tool-tip-content')}>
                      <div className={cx('header')}>vCPU 사용 현황</div>
                      {processInfo.instanceUsed.map(
                        ({ name, resources, type }, index) => (
                          <div key={index} className={cx('used-box')}>
                            <span className={cx('deploy-type', type)}>
                              {INSTANCE_KEY[type]}
                            </span>
                            <div className={cx('info')}>
                              <span>{name}</span>
                              <span className={cx('resource')}>
                                {resources.cpu} Cores
                              </span>
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  }
                />
              )}
            </span>
            <div className={cx('info')}>
              {processInfo.cpu ? (
                <>
                  <span>{processInfo.cpu}</span>
                  <span>Cores</span>
                </>
              ) : (
                <span>-</span>
              )}
            </div>
          </div>
          <div className={cx('detail')}>
            <span className={cx('type')}>
              <div
                className={cx(
                  'condition',
                  processInfo.ramCondition && 'enough',
                )}
              >
                {processInfo.ramCondition ? '여유' : '부족'}
              </div>
              <span>RAM</span>
              {!processInfo.ramCondition && (
                <ProcessToolTip
                  icon={info}
                  position={'up'}
                  iconStyle={{ transform: 'translateY(2px)' }}
                  customStyle={{
                    height: '200px',
                    width: '300px',
                    padding: '24px',
                    transform: 'translate(20px, -10px)',
                  }}
                  contents={
                    <div className={cx('tool-tip-content')}>
                      <div className={cx('header')}>RAM 사용 현황</div>
                      {processInfo.instanceUsed.map(
                        ({ name, resources, type }, index) => (
                          <div key={index} className={cx('used-box')}>
                            <span className={cx('deploy-type', type)}>
                              {INSTANCE_KEY[type]}
                            </span>
                            <div className={cx('info')}>
                              <span>{name}</span>
                              <span className={cx('resource')}>
                                {resources.ram} GB
                              </span>
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  }
                />
              )}
            </span>
            <div className={cx('info')}>
              {processInfo.ram ? (
                <>
                  <span>{processInfo.ram}</span>
                  <span>GB</span>
                </>
              ) : (
                <span>-</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InfoDetail;
