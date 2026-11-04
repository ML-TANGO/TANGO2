import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { callApi, STATUS_SUCCESS } from '@src/network';

import DevToolCard from './DevToolCard';

import classNames from 'classnames/bind';
import style from './DevToolPage.module.scss';

const cx = classNames.bind(style);

const DevToolPage = ({ did, wid }) => {
  const { t } = useTranslation();
  const [toolCardList, setToolCardList] = useState([]);

  const DEV_TOOLS = [
    {
      label: t('createTool.label', { tool: 'VSCode' }),
      type: 'vscode',
      tool: 7,
    },
    {
      label: t('createTool.label', { tool: 'Jupyter Lab' }),
      type: 'jupyter',
      tool: 1,
    },
    {
      label: t('createTool.label', { tool: 'Shell' }),
      type: 'ssh',
      tool: 4,
    },
  ];

  const createDevTool = async (tool) => {
    const response = await callApi({
      url: 'preprocessing/tool/add',
      method: 'post',
      body: {
        preprocessing_id: Number(did),
        preprocessing_tool_type: tool,
      },
    });

    const { status } = response;

    if (status === STATUS_SUCCESS) {
      fetchDevTool();
    }
  };

  const fetchDevTool = async () => {
    const response = await callApi({
      url: `preprocessing/tool?preprocessing_id=${did}`,
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      const { integrated_tool, tool_resource, preprocessing_info } = result;
      const { ram, cpu } = tool_resource;
      const list = integrated_tool.map(
        ({
          gpu_count,
          id,
          image_name,
          tool_type_name,
          status,
          tool_commit_status,
          gpu_cluster_ips,
        }) => ({
          type: tool_type_name,
          id,
          image: image_name,
          gpu: gpu_count,
          status: status.status,
          reason: status.reason,
          ram,
          cpu,
          commitStatus: tool_commit_status,
          ip: gpu_cluster_ips[0]?.ip,
          instance: preprocessing_info.instance_name,
          instanceType: preprocessing_info.instance_type,
        }),
      );

      setToolCardList(list);
    }
  };

  useEffect(() => {
    fetchDevTool();

    const intervalFetchDevTool = setInterval(() => {
      fetchDevTool();
    }, 1000);

    return () => {
      clearInterval(intervalFetchDevTool);
    };
  }, []);

  return (
    <div className={cx('container')}>
      <div className={cx('addBtn-box')}>
        {DEV_TOOLS.map(({ label, type, tool }) => (
          <div
            key={type}
            className={cx('btn')}
            onClick={() => createDevTool(tool)}
          >
            <div className={cx('left-side')}>
              <img
                width={40}
                height={40}
                src={`/images/icon/ic-${type}.svg`}
                alt='icon'
              />
              <span>{label}</span>
            </div>
            <div className={cx('right-side')}>
              <svg
                xmlns='http://www.w3.org/2000/svg'
                width='20'
                height='20'
                viewBox='0 0 20 20'
                fill='none'
              >
                <rect y='9' width='20' height='1' fill='#7E7E7F' />
                <rect
                  x='9'
                  y='20'
                  width='20'
                  height='1'
                  transform='rotate(-90 9 20)'
                  fill='#7E7E7F'
                />
              </svg>
            </div>
          </div>
        ))}
      </div>
      {toolCardList.length === 0 && (
        <div className={cx('empty-tool')}>개발 도구를 생성해 주세요.</div>
      )}
      {toolCardList.length > 0 && (
        <div className={cx('card-container')}>
          {toolCardList.map(
            ({
              type,
              status,
              image,
              gpu,
              cpu,
              ram,
              id,
              reason,
              commitStatus,
              ip,
              instance,
              instanceType,
            }) => (
              <DevToolCard
                key={id}
                id={id}
                type={type}
                status={status}
                image={image}
                gpu={gpu}
                cpu={cpu}
                ram={ram}
                did={did}
                wid={wid}
                reason={reason}
                commitStatus={commitStatus}
                ip={ip}
                instance={instance}
                instanceType={instanceType}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
};

export default DevToolPage;
