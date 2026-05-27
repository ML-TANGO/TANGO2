import { useEffect, useState } from 'react';
import { useRouteMatch } from 'react-router-dom';

import { callApi, STATUS_SUCCESS } from '@src/network';

import ToolCard from '../ToolCard';

import classNames from 'classnames/bind';
import style from './ToolCardList.module.scss';

const cx = classNames.bind(style);

const initialToolInfo = {
  integratedToolList: [],
  toolResource: {
    cpu: 0,
    ram: 0,
    resourceName: '',
  },
};

const ToolCardList = () => {
  const match = useRouteMatch();
  const { tid } = match.params;

  const [integratedToolInfo, setIntegratedToolInfo] = useState(initialToolInfo);
  const { integratedToolList, toolResource } = integratedToolInfo;

  useEffect(() => {
    const getToolList = async () => {
      const response = await callApi({
        url: `projects/tool?project_id=${tid}`,
        method: 'GET',
      });
      const { status, result } = response;

      if (status === STATUS_SUCCESS) {
        // const queueToolList = result.queue_tool;
        const integratedToolList = result.integrated_tool.map(
          (integrateToolData) => {
            const { function_info: functionInfoArr } = integrateToolData;

            const runEnvArr = [];
            const runningInfoArr = [];
            return {
              ...integrateToolData,
              runEnvArr,
              runningInfoArr,
              functionInfoArr,
            };
          },
        );

        setIntegratedToolInfo({
          integratedToolList,
          toolResource: {
            cpu: result.tool_resource.cpu,
            ram: result.tool_resource.ram,
            resourceName: result.project_info?.resource_name,
          },
        });
      }
    };

    getToolList();

    const intervalToolInfo = setInterval(() => {
      getToolList();
    }, 1000);

    return () => {
      clearInterval(intervalToolInfo);
    };
  }, [tid]);

  return (
    <div className={cx('tool-list')}>
      {integratedToolList.map((data) => {
        return (
          <ToolCard
            key={data.id}
            id={data.id}
            data={data}
            toolResource={toolResource}
            tool_type={data.tool_type}
            tool_type_name={data.tool_type_name}
            status={data.status}
            functionInfoArr={data.functionInfoArr}
            on_off_possible={data.on_off_possible}
            tool_commit_status={data.tool_commit_status}
            isHideExplanation={false}
            isPermission={false}
          />
        );
      })}
    </div>
  );
};

export default ToolCardList;
