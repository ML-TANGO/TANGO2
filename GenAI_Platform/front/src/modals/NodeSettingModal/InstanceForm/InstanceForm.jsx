import { ButtonV2 } from '@jonathan/ui-react';

import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import {
  calDeleteInstanceList,
  calFreeGpuList,
  calLastInstanceListIndex,
  changeForm,
  getInstanceName,
  handleResource,
  handleValidate,
  isCheckCpuList,
  isCheckGpuList,
  isCheckGpuListValue,
  isValidateAddBtn,
  postInstanceValidation,
  postValidation,
  RESOURCE_TYPE,
} from '../util';

import InstanceNameInput from '../InstanceNameInput';
import InstanceTypeInput from '../InstanceTypeInput';
import InstanceValidator from '../InstanceValidator';
import NodeGpuSetting from '../NodeGpuSetting';
import VcpuInput from '../VcpuInput';
import VramInput from '../VramInput';

import classNames from 'classnames/bind';
import style from './InstanceForm.module.scss';

const cx = classNames.bind(style);

const InstanceForm = ({
  idx,
  nodeId,
  instanceInfo,
  instanceList,
  freeGpuList,
  last_free_resource,
  setInstanceList,
  handleAllClear,
}) => {
  const { t } = useTranslation();

  // ** 인스턴스 타입 RadioList 받아오는 함수 **
  const getRadioTypeOptions = (idx, instance_list, freeGpuList) => {
    return [
      {
        label: `GPU ${t('instance.label')}`,
        value: `GPU-${idx}`,
        disabled: isCheckGpuList(freeGpuList),
        labelStyle: { fontFamily: 'SpoqaM', fontSize: '14px' },
      },
      {
        label: `CPU ${t('instance.label')}`,
        value: `CPU-${idx}`,
        disabled: isCheckCpuList(instance_list),
        labelStyle: { fontFamily: 'SpoqaM', fontSize: '14px' },
      },
    ];
  };

  // ** 에러 메세지 출력 함수 **
  const handleValidateErrorMsg = (instanceInfo) => {
    const {
      instance_type,
      gpu_name,
      gpu_allocate,
      cpu_allocate,
      ram_allocate,
      instance_validation,
      instance_check_validation,
      instance_name,
    } = instanceInfo;

    const isCheckGpuListTrue = isCheckGpuListValue(freeGpuList);

    if (instance_type === 'GPU') {
      if (!instance_validation && !isCheckGpuListTrue && !instance_name)
        return t('node.settingModal.gpuModel.errorMsg');
      if (!gpu_name) return t('node.settingModal.gpuModel.errorMsg');
      if (!gpu_allocate) return t('node.settingModal.gpuAllocate.errorMsg');
    }

    if (!cpu_allocate) return t('node.settingModal.cpuAllocate.errorMsg');
    if (!ram_allocate) return t('node.settingModal.ramAllocate.errorMsg');
    if (!instance_check_validation) return t('node.validateBtn.message.label');
    return t('node.instance.fail.message');
  };

  // ** [추가 핸들러] **
  const handleAdd = (
    freeGpuList,
    instance_list,
    last_free_resource,
    setInstanceList,
  ) => {
    const updateInstanceList = changeForm(
      instance_list,
      freeGpuList.length > 0 ? 'GPU' : 'CPU',
      last_free_resource,
    );
    setInstanceList((prev) => {
      return {
        ...prev,
        instance_list: updateInstanceList,
      };
    });
  };

  // ** [삭제 핸들러] 삭제를 원하는 리스트의 포함 값 뒤로 전체 삭제 **
  const handleDelete = useCallback(
    async (idx, nodeId, instance_list, setInstanceList) => {
      const deleteInstanceList = calDeleteInstanceList(instance_list, idx);
      await postValidation(nodeId, deleteInstanceList, setInstanceList);
    },
    [],
  );

  const handleInstanceType = async (e, idx, instanceList, setInstanceList) => {
    const newType = e.target.value.split('-')[0];

    const deleteInstanceList = calDeleteInstanceList(instanceList, idx);

    const { result } = await postInstanceValidation(nodeId, deleteInstanceList);
    const { instance_list, last_free_resource, node_gpu_list } = result;

    // ** freeGpu 값 formInstanceList 상태에서 관리 **
    const freeGpuList = calFreeGpuList(
      last_free_resource.gpu_id_list,
      node_gpu_list,
    );

    // ** CPU 값 체크 **
    const isCpuValue = isCheckCpuList(instance_list);

    // ** instanceList 마지막 값 추가 **
    const updateInstanceList = changeForm(
      instance_list,
      newType,
      last_free_resource,
    );

    setInstanceList({
      ...result,
      instance_list: updateInstanceList,
      freeGpuList,
      isCpuValue,
    });
  };

  // ** 추가 버튼 disabled 로직 함숨 **
  const isAddBtnDisabled = useMemo(() => {
    const isValidationBtn = instanceList.find(
      (info) => info.instance_validation === false,
    );
    if (isValidationBtn) return true;

    const isValidateAddBtnValue = isValidateAddBtn(
      idx,
      instanceList,
      freeGpuList,
      last_free_resource,
    );
    if (!isValidateAddBtnValue) return true;

    return false;
  }, [idx, instanceList, freeGpuList, last_free_resource]);

  // ** 마지막 인덱스인지 확인 변수 **
  const isLastInstanceList = useMemo(() => {
    const isLastIndex = calLastInstanceListIndex(instanceList, idx);
    return isLastIndex;
  }, [idx, instanceList]);

  return (
    <div className={cx('input-group')}>
      <div className={cx('create-title-cont')}>
        <span className={cx('text')}>{t('instanceCreate.label')}</span>
        {!instanceInfo.instance_validation && (
          <ButtonV2
            label={t('validateTest')}
            colorType='skyblue'
            size='l'
            style={{ position: 'absolute', top: 0, right: 0 }}
            onClick={() =>
              handleValidate(
                nodeId,
                instanceInfo,
                instanceList,
                setInstanceList,
              )
            }
            disabled={
              handleValidateErrorMsg(instanceInfo) !==
              t('node.validateBtn.message.label')
            }
          />
        )}
      </div>
      <div>
        <InstanceTypeInput
          idx={idx}
          radioOptions={getRadioTypeOptions(idx, instanceList, freeGpuList)}
          selectedValue={`${instanceInfo.instance_type}-${idx}`}
          onChangeValue={(e) =>
            handleInstanceType(e, idx, instanceList, setInstanceList)
          }
          isValidateBtn={instanceInfo.instance_validation}
          isValidateBtnDisabled={
            handleValidateErrorMsg(instanceInfo) !==
            t('node.validateBtn.message.label')
          }
          handleValidate={handleValidate}
        />
        <InstanceNameInput
          t={t}
          idx={idx}
          value={getInstanceName(instanceInfo)}
          isReadOnly={true}
          disableLeftIcon={true}
          disableClearBtn={true}
        />
        {instanceInfo.instance_type === 'GPU' && (
          <NodeGpuSetting
            idx={idx}
            isValidate={instanceInfo.instance_validation}
            instanceInfo={instanceInfo}
            setInstanceList={setInstanceList}
            freeGpuList={freeGpuList}
          />
        )}
        <div className={cx('flex-cont')}>
          <VcpuInput
            t={t}
            value={instanceInfo.cpu_allocate}
            onChange={(value) =>
              handleResource(idx, value, setInstanceList, RESOURCE_TYPE.CPU)
            }
            max={instanceInfo.free_cpu}
            min={0}
          />
          <VramInput
            t={t}
            value={instanceInfo.ram_allocate}
            onChange={(value) =>
              handleResource(idx, value, setInstanceList, RESOURCE_TYPE.RAM)
            }
            max={instanceInfo.free_ram}
            min={0}
          />
        </div>
        <InstanceValidator
          t={t}
          isValidate={instanceInfo.instance_validation}
          isLastInstanceList={isLastInstanceList}
          errorMsg={handleValidateErrorMsg(instanceInfo)}
          instanceName={getInstanceName(instanceInfo)}
          instanceCount={instanceInfo.instance_count}
          isAddBtnDisabled={isAddBtnDisabled}
          handleDelete={() =>
            handleDelete(idx, nodeId, instanceList, setInstanceList)
          }
          handleAdd={() =>
            handleAdd(
              freeGpuList,
              instanceList,
              last_free_resource,
              setInstanceList,
            )
          }
          handleAllClear={handleAllClear}
        />
      </div>
    </div>
  );
};

export default InstanceForm;
