import { loadModalComponent } from '@src/modal';
import { useEffect } from 'react';

import UserWorkbenchContent from '@src/components/pageContents/user/UserWorkbenchContent';

/**
 * 에디터
 * - (option) 포트포워딩
 *
 * jupyter
 * - 프토포워딩
 * - 도커이미지
 * - gpu model count
 *
 * job, hps
 * - 도커이미지
 * - gpu model count
 */

function UserWorkbenchPage() {
  // const match = useRouteMatch();
  // const { tid } = match.params;

  // const [integratedToolList, setIntegratedToolList] = useState([]);
  // const [toolResource, setToolResource] = useState({
  //   cpu: 0,
  //   ram: 0,
  //   resoureceName: '',
  // });
  // const getToolList = useCallback(async () => {
  //   const response = await callApi({
  //     url: `projects/tool?project_id=${tid}`,
  //     method: 'GET',
  //   });
  //   const { status, result } = response;

  //   if (status === STATUS_SUCCESS) {
  //     // const queueToolList = result.queue_tool;
  //     const integratedToolList = result.integrated_tool.map((t) => {
  //       const { function_info: functionInfoArr } = t;

  //       const runEnvArr = [];
  //       const runningInfoArr = [];

  //       return { ...t, runEnvArr, runningInfoArr, functionInfoArr };
  //     });

  //     // setQueueToolList(queueToolList);
  //     setIntegratedToolList(integratedToolList);
  //     setToolResource({
  //       cpu: result.tool_resource.cpu,
  //       ram: result.tool_resource.ram,
  //       resourceName: result.project_info?.resource_name,
  //     });
  //     return true;
  //   }
  //   return false;
  // }, [tid]);

  // ** 자원 사용 중인 모든 액션 종료
  // const onStopAllTool = async () => {
  //   setStopLoading(true);
  //   const response = await callApi({
  //     url: `trainings/stop?training_id=${tid}`,
  //     method: 'get',
  //   });
  //   setStopLoading(false);
  //   const { status, message, error } = response;
  //   if (status === STATUS_SUCCESS) {
  //     defaultSuccessToastMessage('stop');
  //   } else {
  //     errorToastMessage(error, message);
  //   }
  // };

  // const renderMap = useMemo(
  //   () => ({
  //     port_forwarding_info: (arr) => {
  //       return <PortInfo portList={arr} />;
  //     },
  //     gpu_model: (gpus = []) => {
  //       if (!gpus) return '-';
  //       return (
  //         <div>
  //           {gpus.map(({ model, node_list: nodeList }, key) => (
  //             <div key={key}>
  //               <div>{model}</div>
  //               <div>{nodeList.map((n) => n)}</div>
  //             </div>
  //           ))}
  //         </div>
  //       );
  //     },
  //     gpu_count: (count) => count,
  //   }),
  //   [],
  // );

  /**
   * Action 브래드크럼
   * @param {String} trainingName
   */
  // const breadCrumbHandler = (trainingName) => {
  //   dispatch(
  //     startPath([
  //       {
  //         component: {
  //           name: 'Training',
  //           path: `/user/workspace/${wid}/trainings`,
  //           t,
  //         },
  //       },
  //       {
  //         component: {
  //           name: trainingName,
  //         },
  //       },
  //       {
  //         component: { name: 'Workbench', t },
  //       },
  //     ]),
  //   );
  // };

  // useIntervalCall(getToolList, 1000);

  useEffect(() => {
    loadModalComponent('TOOL_GPU_ALLOCATE');
    loadModalComponent('CREATE_DOCKER_IMAGE');
    loadModalComponent('SSH_CONNECTION_GUIDE');
    loadModalComponent('TOOL_PASSWORD_CHANGE');
    loadModalComponent('VISUALIZATION_GUIDE');
  }, []);

  return <UserWorkbenchContent />;
}

export default UserWorkbenchPage;
