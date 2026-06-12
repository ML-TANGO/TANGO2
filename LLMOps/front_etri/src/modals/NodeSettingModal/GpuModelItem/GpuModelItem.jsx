import { Checkbox, InputNumber } from '@tango/ui-react';

// import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import { handleResource, RESOURCE_TYPE } from '../util';

import classNames from 'classnames/bind';
import style from './GpuModelItem.module.scss';

const cx = classNames.bind(style);

const GpuModelItem = ({
  type,
  idx,
  checkBoxIdx,
  modelName,
  totalGpu,
  vram,
  isCheck,
  instanceInfo,
  setInstanceList,
}) => {
  // ** GPU 체크 박스 선택 함수 **
  const handleGpuCheck = (e, checkBoxIdx, idx, type, setInstanceList) => {
    if (type === 'InstanceList') return;

    setInstanceList((prev) => {
      const shallowCopyList = prev.freeGpuList.slice();
      const findCheckObj = shallowCopyList[checkBoxIdx];

      const changeCheckList = shallowCopyList.map((el, index) => {
        if (index === checkBoxIdx) {
          return {
            ...el,
            isCheck: e.target.checked,
          };
        }

        return {
          ...el,
          isCheck: false,
        };
      });

      const shallowInstanceList = prev.instance_list.slice();

      if (changeCheckList[checkBoxIdx].isCheck) {
        shallowInstanceList[idx].gpu_name = findCheckObj.gpu_name;
        shallowInstanceList[idx].gpu_group_id = findCheckObj.gpu_group_id;
        shallowInstanceList[idx].gpu_total = findCheckObj.gpu_total;
        shallowInstanceList[idx].gpu_vram = findCheckObj.gpu_vram;
      } else {
        shallowInstanceList[idx].gpu_name = '';
      }
      shallowInstanceList[idx].gpu_allocate = null;

      return {
        ...prev,
        instance_list: shallowInstanceList,
        freeGpuList: changeCheckList,
      };
    });
  };

  return (
    <div className={cx('list-item')}>
      <div className={cx('check')}>
        <div className={cx('check-label-cont')}>
          <Checkbox
            label={modelName}
            customLabelStyle={{
              padding: '0 0 0 3px',
              fontSize: '14px',
            }}
            name={`gpuModel${checkBoxIdx}`}
            checked={isCheck}
            onChange={(e) =>
              handleGpuCheck(e, checkBoxIdx, idx, type, setInstanceList)
            }
            disabled={type === 'instanceList'}
          />
        </div>
        {/* <InstanceTooltip /> */}
      </div>
      <div className={cx('sub-row')}>{totalGpu} EA</div>
      <div className={cx('sub-row')}>{vram} GB</div>
      <InputNumber
        placeholder={`사용가능: ${totalGpu}`}
        onChange={({ value }) =>
          handleResource(idx, value, setInstanceList, RESOURCE_TYPE.GPU)
        }
        value={isCheck ? instanceInfo.gpu_allocate : 0}
        max={totalGpu}
        min={0}
        isReadOnly={!isCheck}
      />
    </div>
  );
};

export default GpuModelItem;
