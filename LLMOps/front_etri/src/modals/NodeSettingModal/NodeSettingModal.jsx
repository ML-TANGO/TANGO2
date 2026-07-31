import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import { toast } from '@src/components/Toast';

import { closeModal } from '@src/store/modules/modal';
import {
  handleClosePopup,
  handleOpenPopup,
} from '@src/store/modules/popupState';
import { callApi } from '@src/network';

import InstanceForm from './InstanceForm';

import { executeWithLogging } from '@src/utils';
import { calFreeGpuList, changeForm, isCheckCpuList } from './util';

import classNames from 'classnames/bind';
import style from './NodeSettingModal.module.scss';

const cx = classNames.bind(style);

const initialInstanceList = {
  instance_list: [
    {
      instance_type: 'CPU',
      gpu_name: '',
      gpu_allocate: 0,
      cpu_allocate: 0,
      ram_allocate: 0,
      instance_validation: false,
      instance_name: '',
    },
  ],
  last_free_resource: {
    cpu: 0,
    gpu_id_list: [],
    ram: 0,
  },
  node_gpu_list: [],
};

// ** [Footer validate Message] **
const validateMessage = (t, instanceList, last_free_resource) => {
  const shallowCopyList = instanceList.slice();
  const message = shallowCopyList.reduce((acc, info) => {
    const {
      instance_type,
      gpu_name,
      gpu_allocate,
      cpu_allocate,
      ram_allocate,
      instance_validation,
    } = info;

    if (instance_type === 'GPU') {
      if (!gpu_name || !gpu_allocate)
        return t('node.virtualSettingModal.instanceInfo.warn.message');
    }

    if (!cpu_allocate || !ram_allocate)
      return t('node.virtualSettingModal.instanceInfo.warn.message');

    if (!instance_validation)
      return t('node.virtualSettingModal.validate.warn.message');

    const { cpu, ram } = last_free_resource;
    if (cpu === 0 || ram === 0)
      return (
        <p style={{ color: 'blue', margin: 'inherit' }}>
          {t('node.virtualSettingModal.success.message')}
        </p>
      );
    return null;
  }, null);

  return message;
};

const NodeSettingModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { nodeId } = data;
  const title = t('node.setting.label');

  const [instanceList, setInstanceList] = useState(initialInstanceList);
  const { instance_list, last_free_resource, freeGpuList } = instanceList;

  // ** [저장 validate] **
  const isValidateSaveBtn = (instanceList) => {
    const shallowCopyList = instanceList.slice();

    const falseValidationValue = shallowCopyList.find(
      ({ instance_validation }) => !instance_validation,
    );
    return !falseValidationValue;
  };

  //  ** [SAVE API] **
  const postSaveApi = async (nodeId, instance_list) => {
    executeWithLogging(async () => {
      const { status, message } = await callApi({
        url: 'nodes/instance',
        method: 'put',
        body: {
          node_id: nodeId,
          instance_list: instance_list,
        },
      });

      if (status === 'STATUS_FAIL') return toast.error(message);
      dispatch(closeModal(type));
      dispatch(handleClosePopup());
    });
  };

  // ** [제출 저장 핸들러] **
  const handleSubmit = (nodeId, instance_list, dispatch, postSaveApi) => {
    dispatch(
      handleOpenPopup({
        popupTitle: t('node.virtualSettingModal.confirm.title'),
        popupContents: t('node.virtualSettingModal.confirm.contents'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('accept.label'),
        handleSubmit: async () => {
          await postSaveApi(nodeId, instance_list);
        },
      }),
    );
  };

  // ** [인스턴스 초기화 핸들러] **
  const handleAllClear = (nodeId) => {
    dispatch(
      handleOpenPopup({
        type: 'main',
        popupTitle: t('node.virtualSettingModal.allClear'),
        popupContents: t('node.virtualSettingModal.confirm.contents'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('accept.label'),
        handleSubmit: async () => {
          await postSaveApi(nodeId, []);
        },
      }),
    );
  };

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    const getInstanceNode = () => {
      executeWithLogging(async () => {
        const { result } = await callApi({
          url: `nodes/instance?node_id=${nodeId}`,
          method: 'get',
          signal,
        });
        const { instance_list, last_free_resource, node_gpu_list } = result;

        // ** freeGpu 값 formInstanceList 상태에서 관리 **
        const freeGpuList = calFreeGpuList(
          last_free_resource.gpu_id_list,
          node_gpu_list,
        );

        // ** CPU 값 체크 **
        const isCpuValue = isCheckCpuList(instance_list);

        // ** instanceList 0일 때도 고려**
        const instanceListZero = changeForm([], 'GPU', last_free_resource);

        const copyInstanceList = instance_list.slice();
        const newInstanceList = copyInstanceList.map((el) => {
          return {
            ...el,
            instance_check_validation: el.instance_validation,
          };
        });

        setInstanceList({
          ...result,
          instance_list:
            instance_list.length === 0 ? instanceListZero : newInstanceList,
          freeGpuList,
          isCpuValue,
        });
      });
    };

    getInstanceNode();

    return () => {
      controller.abort();
    };
  }, [nodeId]);

  return (
    <NewStyleModalFrame
      submit={{
        text: t('saveBtn.label'),
        func: () => {
          handleSubmit(nodeId, instance_list, dispatch, postSaveApi);
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      type={type}
      validate={isValidateSaveBtn(instance_list)}
      isResize={true}
      isMinimize={true}
      title={title}
      footerMessage={validateMessage(t, instance_list, last_free_resource)}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('modal-content')}>
        {instance_list.length > 0 &&
          instance_list.map((instanceInfo, idx) => (
            <InstanceForm
              key={idx}
              idx={idx}
              nodeId={nodeId}
              instanceInfo={instanceInfo}
              instanceList={instance_list}
              freeGpuList={freeGpuList}
              last_free_resource={last_free_resource}
              setInstanceList={setInstanceList}
              handleAllClear={() => handleAllClear(nodeId)}
            />
          ))}
      </div>
    </NewStyleModalFrame>
  );
};

export default NodeSettingModal;
