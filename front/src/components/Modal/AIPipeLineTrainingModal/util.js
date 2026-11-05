import {
  getPipelineOptionImages,
  getPipelineOptionItems,
  getPipelineRunCode,
} from '@src/apis/flightbase/pipeline';

import { toast } from '@src/components/Toast';

import { STATUS_SUCCESS } from '@src/network';

export const getPipeLineProjectOptions = async (
  workspaceId,
  taskType,
  stateName,
  setOptions,
) => {
  const { result, status, message } = await getPipelineOptionItems(
    workspaceId,
    taskType,
  );
  if (status === STATUS_SUCCESS) {
    if (result.length === 0) {
      setOptions((prev) => ({
        ...prev,
        [stateName]: [],
      }));
      return;
    }

    const options = result.map((info) => {
      const { id: value, name: label } = info;
      return {
        ...info,
        value,
        label,
      };
    });
    setOptions((prev) => ({
      ...prev,
      [stateName]: options,
    }));
  } else {
    toast.error(message);
  }
};

export const getDockerImageList = async (
  workspaceId,
  stateName,
  setOptions,
) => {
  const { result, status, message } = await getPipelineOptionImages(
    workspaceId,
  );
  if (status === STATUS_SUCCESS) {
    if (result.length === 0) {
      setOptions((prev) => ({
        ...prev,
        [stateName]: [],
      }));
      return;
    }

    const dockerImageOptions = result.map((info) => {
      const { id: value, name: label } = info;
      return {
        value,
        label,
      };
    });
    setOptions((prev) => ({
      ...prev,
      [stateName]: dockerImageOptions,
    }));
  } else {
    toast.error(message);
  }
};

export const getRunCodeOptions = async (
  projectId,
  taskType,
  stateName,
  setOptions,
) => {
  const { result, status, message } = await getPipelineRunCode(
    projectId,
    taskType,
  );
  if (status === STATUS_SUCCESS) {
    if (result.length === 0) {
      setOptions((prev) => ({
        ...prev,
        [stateName]: [],
      }));
      return;
    }

    const options = result.map((info) => {
      return {
        value: info,
        label: info,
      };
    });
    setOptions((prev) => ({
      ...prev,
      [stateName]: options,
    }));
  } else {
    toast.error(message);
  }
};

export const calSelectedInstanceInfo = (projectOptions, project) => {
  const emptyValue = {
    resource_name: '-',
    gpu_allocate: 0,
  };
  if (!project) return emptyValue;
  const selectedInfo = projectOptions.find((info) => info.value === project);
  return selectedInfo ?? emptyValue;
};
