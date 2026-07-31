// i18n
import { withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { openModal } from '@src/store/modules/modal';

import { bytesToGB } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AdminNodeDetail.module.scss';

const cx = classNames.bind(style);

const AdminNodeDetail = ({ data, t }) => {
  const dispatch = useDispatch();

  const {
    cpu_info,
    gpu_info,
    hostname,
    mem_info,
    nvidia_driver,
    os_version,
    sw_version,
    instance: instanceList,
  } = data;
  const { cpu_core, cpu_model } = cpu_info;
  const { container_rumtime, kubernets } = sw_version;
  const { mem_total } = mem_info;

  const gpuInfoList = gpu_info ? Object.values(gpu_info) : [];

  // const onClickSettingModal = (migMode) => {
  //   dispatch(
  //     openModal({
  //       modalType: 'MIG_SETTING_MODAL',
  //       modalData: {
  //         submit: {
  //           func: () => {
  //             console.log('저장하기');
  //           },
  //         },
  //         data: migMode,
  //       },
  //     }),
  //   );
  // };

  const getGpuConfiguration = (instanceType, gpuName, count) => {
    if (instanceType === 'GPU') return `${gpuName} x ${count}EA`;
    return '-';
  };

  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <h3 className={cx('title')}>
          {t('detailsOf.label', { name: `${hostname}` })}
        </h3>
      </div>
      <ul className={cx('horizon-box')}>
        <li className={cx('box')}>
          <span className={cx('label')}>CPU</span>
          <span className={cx('value')}>{cpu_model || '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>CPU Cores</span>
          <span className={cx('value')}>{cpu_core || '-'} cores</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>OS</span>
          <span className={cx('value')}>{os_version || '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>RAM</span>
          <span className={cx('value')}>
            {`${bytesToGB(mem_total)} GB` || '-'}
          </span>
        </li>
      </ul>
      <ul className={cx('horizon-box')}>
        <li className={cx('box')}>
          <span className={cx('label')}>NVIDIA Driver</span>
          <span className={cx('value')}>{nvidia_driver || '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>Kubernets</span>
          <span className={cx('value')}>{kubernets || '-'}</span>
        </li>
        <li className={cx('box')}>
          <span className={cx('label')}>Container Runtime</span>
          <span className={cx('value')}>{container_rumtime || '-'}</span>
        </li>
      </ul>
      {gpuInfoList.length !== 0 && (
        <div className={cx('block')}>
          <p className={cx('block-title')}>{t('gpuInformation.label')}</p>
          <table className={cx('info-table')}>
            <thead>
              <tr>
                <th>GPU {t('id.label')}</th>
                <th>{t('template.model.label')}</th>
                <th>{t('memory.label')}</th>
                <th>CUDA Cores</th>
                <th>{t('node.Architecture')}</th>
                <th>NVLink</th>
                <th>{t('node.migMode.label')}</th>
                <th>{t('migSetting.label')}</th>
              </tr>
            </thead>
            <tbody>
              {gpuInfoList.map(
                (
                  {
                    gpu_mem,
                    model_name,
                    cuda_cores,
                    architecture,
                    nvlink,
                    mig_mode,
                  },
                  idx,
                ) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>{model_name}</td>
                    <td>{gpu_mem} MB</td>
                    <td>{cuda_cores} cores</td>
                    <td>{architecture}</td>
                    <td>{nvlink ? 'On' : 'Not Supported'}</td>
                    <td>{mig_mode ? `${mig_mode}EA` : 'Not Supported'}</td>
                    <td>
                      {/* {mig_mode ? (
                        <img
                          className='table-icon'
                          src='/images/icon/00-ic-basic-pen.svg'
                          alt='edit'
                          onClick={() => onClickSettingModal(mig_mode)}
                        />
                      ) : ( */}
                      -{/* )} */}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
      {instanceList.length !== 0 && (
        <div className={cx('block')}>
          <p className={cx('block-title')}>{t('node.virtualInfo')}</p>
          <table className={cx('info-table')}>
            <thead>
              <tr>
                <th>{t('instanceName.label')}</th>
                <th>{t('gpuConfig.label')}</th>
                <th>vCPU</th>
                <th>RAM</th>
              </tr>
            </thead>
            <tbody>
              {instanceList.map(
                ({
                  instance_name,
                  instance_type,
                  gpu_name,
                  gpu_allocate,
                  cpu_allocate,
                  ram_allocate,
                  instance_id,
                }) => (
                  <tr key={instance_id}>
                    <td>{instance_name}</td>
                    <td>
                      {getGpuConfiguration(
                        instance_type,
                        gpu_name,
                        instance_type === 'GPU' ? gpu_allocate : cpu_allocate,
                      )}
                    </td>
                    <td>{cpu_allocate} cores</td>
                    <td>{ram_allocate} GB</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default withTranslation()(AdminNodeDetail);
