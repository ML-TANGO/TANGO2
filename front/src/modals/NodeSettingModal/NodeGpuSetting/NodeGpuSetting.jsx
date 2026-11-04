import { useTranslation } from 'react-i18next';

import { calRemoveNvidia } from '../util';

import GpuModelItem from '../GpuModelItem';

import classNames from 'classnames/bind';
import style from './NodeGpuSetting.module.scss';

const cx = classNames.bind(style);

const NodeGpuSetting = ({
  idx,
  isValidate,
  instanceInfo,
  setInstanceList,
  freeGpuList,
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('gpu-setting-cont')}>
      <div className={cx('gpuSetting-cont')}>
        <span className={cx('gpuSetting-title')}>{t('gpuSetting.label')}</span>
      </div>
      <div className={cx('wrapper')}>
        <div className={cx('list-header')}>
          <div>{t('modelName.label')}</div>
          <div className={cx('sub-col')}>
            <span>{t('totalAmount.label')}</span>
          </div>

          <div className={cx('sub-col')}>
            <span>VRAM</span>
          </div>

          <div className={cx('sub-col')}>
            <span>{t('allocation.label')}</span>
          </div>
        </div>
        {!isValidate && !instanceInfo.instance_name ? (
          freeGpuList.map((freeInstanceInfo, freeGpuIdx) => (
            <GpuModelItem
              key={freeGpuIdx}
              type='form'
              idx={idx}
              checkBoxIdx={freeGpuIdx}
              modelName={calRemoveNvidia(freeInstanceInfo.gpu_name)}
              totalGpu={freeInstanceInfo.gpu_total}
              vram={freeInstanceInfo.gpu_vram}
              isCheck={freeInstanceInfo.isCheck}
              instanceInfo={instanceInfo}
              setInstanceList={setInstanceList}
            />
          ))
        ) : (
          <GpuModelItem
            type='instanceList'
            idx={idx}
            checkBoxIdx={idx}
            modelName={instanceInfo.gpu_name}
            totalGpu={instanceInfo.gpu_total}
            vram={instanceInfo.gpu_vram}
            isCheck={true}
            instanceInfo={instanceInfo}
            setInstanceList={setInstanceList}
          />
        )}
      </div>
    </div>
  );
};

export default NodeGpuSetting;
