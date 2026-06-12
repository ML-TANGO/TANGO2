import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { Badge } from '@tango/ui-react';

import _ from 'lodash';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';
import DefaultResource from './DefaultResource';
import ProjectResource from './ProjectResource';
import Tab from './Tab';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// ** 초깃값 **
export const itemType = {
  project: (t) => {
    return {
      label: t('training'),
      color: 'orange',
    };
  },
  deployment: (t) => {
    return {
      label: t('deployment'),
      color: 'primary-2',
    };
  },
  preprocessing: (t) => {
    return {
      label: t('preprocessing'),
      color: 'green',
    };
  },
};

const rangeInitial = {
  learningToolCpu: 0,
  learningToolRam: 0,
  jobToolCpu: 0,
  jobToolRam: 0,
  workerCpu: 0,
  workerRam: 0,
};

const selectedProjectInitial = {
  item_type: '',
  item_id: 0,
  name: '',
  job_cpu_limit: 0,
  job_ram_limit: 0,
  tool_cpu_limit: 0,
  tool_ram_limit: 0,
  deployment_cpu_limit: 0,
  deployment_ram_limit: 0,
  value: 0,
};

// ** [API] **
export const getWorkspaceResource = async (
  workspaceId,
  setRange,
  setMaxRange,
) => {
  const response = await callApi({
    url: `workspaces/resource?workspace_id=${workspaceId}`,
    method: 'GET',
  });

  const { status, result } = response;
  if (status === STATUS_SUCCESS) {
    const {
      cpu_max_limit,
      ram_max_limit,
      tool_cpu_limit,
      tool_ram_limit,
      job_cpu_limit,
      job_ram_limit,
      hps_cpu_limit,
      hps_ram_limit,
      deployment_cpu_limit,
      deployment_ram_limit,
    } = result;

    setMaxRange({
      cpu: cpu_max_limit,
      ram: ram_max_limit,
    });

    const resource = {
      learningToolCpu: tool_cpu_limit,
      learningToolRam: tool_ram_limit,
      jobToolCpu: job_cpu_limit,
      jobToolRam: job_ram_limit,
      hpsToolCpu: hps_cpu_limit,
      hpsToolRam: hps_ram_limit,
      workerCpu: deployment_cpu_limit,
      workerRam: deployment_ram_limit,
    };

    setRange(resource);
    sessionStorage.setItem('default-resource', JSON.stringify(resource));
  }
};

export const getWorkspaceResourceItem = async (
  workspaceId,
  setProjectInfoList,
  t,
) => {
  const response = await callApi({
    url: `workspaces/resource/items?workspace_id=${workspaceId}`,
    method: 'GET',
  });

  const { status, result, error, message } = response;
  if (status === STATUS_SUCCESS) {
    const transformResult = result.map((el) => {
      return {
        label: el.name,
        value: `${el.item_type}-${el.item_id}`,
        max_cpu: el.max_cpu,
        max_ram: el.max_ram,
        item_type: el.item_type,
        job_cpu_limit: el.job_cpu_limit ?? 0,
        job_ram_limit: el.job_ram_limit ?? 0,
        tool_cpu_limit: el.tool_cpu_limit ?? 0,
        tool_ram_limit: el.tool_ram_limit ?? 0,
        deployment_cpu_limit: el.deployment_cpu_limit ?? 0,
        deployment_ram_limit: el.deployment_ram_limit ?? 0,
        frontContent: (
          <Badge
            label={itemType[el.item_type](t).label}
            type={itemType[el.item_type](t).color}
          />
        ),
        item_id: el.item_id,
      };
    });

    setProjectInfoList(transformResult);
    sessionStorage.setItem('project-resource', JSON.stringify(transformResult));
    return;
  }
  errorToastMessage(error, message);
};

export const putUpdateWorkspaceResource = async (workspaceId, range) => {
  const response = await callApi({
    url: 'workspaces/resource',
    method: 'PUT',
    body: {
      workspace_id: Number(workspaceId),
      tool_cpu_limit: range.learningToolCpu,
      tool_ram_limit: range.learningToolRam,
      job_cpu_limit: range.jobToolCpu,
      job_ram_limit: range.jobToolRam,
      hps_cpu_limit: 0,
      hps_ram_limit: 0,
      deployment_cpu_limit: range.workerCpu,
      deployment_ram_limit: range.workerRam,
    },
  });
  return response;
};

const putWorkspaceResourceItem = async (workspaceId, projectRange) => {
  const {
    item_type,
    tool_cpu_limit,
    tool_ram_limit,
    job_cpu_limit,
    job_ram_limit,
    deployment_cpu_limit,
    deployment_ram_limit,
    item_id,
  } = projectRange;

  const res = await callApi({
    url: 'workspaces/resource/items',
    method: 'PUT',
    body: {
      workspace_id: workspaceId,
      item_type,
      item_id,
      tool_cpu_limit,
      tool_ram_limit,
      job_cpu_limit,
      job_ram_limit,
      hps_cpu_limit: 0,
      hps_ram_limit: 0,
      deployment_cpu_limit,
      deployment_ram_limit,
    },
  });
  return res;
};

// ** 핸들러 **
const handleRangeBar = (setting, value, maxValue, setRange) => {
  setRange((prev) => ({
    ...prev,
    [setting]: Number(value) >= maxValue ? maxValue : Number(value),
  }));
};

const reomveSessionStorage = () => {
  sessionStorage.removeItem('default-resource');
  sessionStorage.removeItem('project-resource');
};

const calReset = (tabValue, defaultRange, projectRange) => {
  if (tabValue === 0) {
    const defaultResource = JSON.parse(
      sessionStorage.getItem('default-resource'),
    );

    if (_.isEqual(defaultRange, defaultResource)) return true;
    return false;
  }

  if (!projectRange.value) {
    return true;
  }
  const projectResource = JSON.parse(
    sessionStorage.getItem('project-resource'),
  );
  const findProjectResource = projectResource.find(
    (el) => el.value === projectRange.value,
  );
  const compare1 = _.omit(findProjectResource, ['frontContent']);
  const compare2 = _.omit(projectRange, ['frontContent']);
  if (_.isEqual(compare1, compare2)) return true;
  return false;
};

const EditWorkspaceResourceModal = ({ type, data }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const title = useMemo(() => {
    return t('workspaceResourceManagement.label');
  }, [t]);
  const { submit, apply, cancel, workspaceId } = data;

  // ** 탭 **
  const [tabValue, setTabValue] = useState(0);

  // ** 기본 자원 관리 **
  const [defaultRange, defaultSetRange] = useState(rangeInitial);
  const [defaultMaxRange, setDefaultMaxRange] = useState({
    cpu: 0,
    ram: 0,
  });

  // ** 프로젝트별 자원 관리 **
  const [projectInfoList, setProjectInfoList] = useState([]);

  const [projectRange, setProjectRange] = useState(selectedProjectInitial);
  const [projectMaxRange, setPorjectMaxRange] = useState({
    cpu: 0,
    ram: 0,
  });

  // ** 버튼 **
  const isResetValidate = calReset(tabValue, defaultRange, projectRange);
  const reset = {
    text: t('setting.reset.label'),
    func: async () => {
      if (tabValue === 0) {
        const defaultResource = JSON.parse(
          sessionStorage.getItem('default-resource'),
        );
        defaultSetRange(defaultResource);
        return;
      }
      const projectResource = JSON.parse(
        sessionStorage.getItem('project-resource'),
      );
      const findProjectResource = projectResource.find(
        (el) => el.value === projectRange.value,
      );
      setProjectRange(findProjectResource);
    },
    isValidate: isResetValidate,
  };

  const transformCancel = useMemo(() => {
    return {
      text: cancel.text,
      func: () => {
        reomveSessionStorage();
        dispatch(closeModal(type));
      },
    };
  }, [cancel.text, type, dispatch]);

  const transformApply = {
    text: apply.text,
    func: async () => {
      if (tabValue === 0) {
        const { status, message, error } = await putUpdateWorkspaceResource(
          workspaceId,
          defaultRange,
        );

        if (status === STATUS_SUCCESS) {
          defaultSuccessToastMessage('create');
          getWorkspaceResource(
            workspaceId,
            defaultSetRange,
            setDefaultMaxRange,
          );
          return;
        }

        errorToastMessage(error, message);
        return;
      }

      if (!projectRange.value) {
        toast.error(t('project.select.label'));
        return;
      }
      const { status, error, message } = await putWorkspaceResourceItem(
        workspaceId,
        projectRange,
      );
      if (status === STATUS_SUCCESS) {
        defaultSuccessToastMessage('create');
        getWorkspaceResourceItem(workspaceId, setProjectInfoList, t);
        return;
      }

      errorToastMessage(error, message);
    },
    isValidate: isResetValidate,
  };

  const transformSubmit = {
    text: submit.text,
    func: async () => {
      let statuses = [];
      if (tabValue === 0) {
        const { status, message, error } = await putUpdateWorkspaceResource(
          workspaceId,
          defaultRange,
        );

        if (status !== STATUS_SUCCESS) {
          errorToastMessage(error, message);
        }
        statuses.push(status);
      }

      if (projectRange.value) {
        const {
          status: status2,
          error: error2,
          message: message2,
        } = await putWorkspaceResourceItem(workspaceId, projectRange);

        statuses.push(status2);
        if (status2 !== STATUS_SUCCESS) {
          errorToastMessage(error2, message2);
        }
      }

      const isAllSuccess = statuses.every(
        (status) => status === STATUS_SUCCESS,
      );

      if (isAllSuccess) {
        defaultSuccessToastMessage('create');
        reomveSessionStorage();
        cancel.func();
      }
    },
  };

  const handleProejectItem = (d) => {
    setProjectRange(d);
    setPorjectMaxRange({
      cpu: d.max_cpu,
      ram: d.max_ram,
    });
  };

  useEffect(() => {
    getWorkspaceResource(workspaceId, defaultSetRange, setDefaultMaxRange);
    getWorkspaceResourceItem(workspaceId, setProjectInfoList, t);
  }, [workspaceId, t]);

  return (
    <NewStyleModalFrame
      type={type}
      title={title}
      submit={transformSubmit}
      apply={transformApply}
      reset={reset}
      cancel={transformCancel}
      validate={tabValue === 1 && projectRange.value === 0 ? false : true}
      isResize={true}
      isMinimize={true}
    >
      <div>
        <Tab tabValue={tabValue} handleTab={setTabValue} />
        {tabValue === 0 && (
          <DefaultResource
            range={defaultRange}
            maxRange={defaultMaxRange}
            handleRangeBar={(setting, value, maxValue) =>
              handleRangeBar(setting, value, maxValue, defaultSetRange)
            }
          />
        )}
        {tabValue === 1 && (
          <ProjectResource
            projectInfoList={projectInfoList}
            range={projectRange}
            maxRange={projectMaxRange}
            handleProejectItem={handleProejectItem}
            handleRangeBar={(setting, value, maxValue) =>
              handleRangeBar(setting, value, maxValue, setProjectRange)
            }
          />
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default withTranslation()(EditWorkspaceResourceModal);
