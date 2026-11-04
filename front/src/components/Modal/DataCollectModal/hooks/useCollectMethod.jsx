import { useCallback, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';

import { closeModal, openModal } from '@src/store/modules/modal';

import {
  handleDeleteCustomApiButton,
  handleModifyCustomApiButton,
} from '../../AddCustomApiModal/AddCustomApiModal';
import { handleFlightbaseDeleteButton } from '../../AddDeployProjectModal/AddDeployProjectModal';
import {
  handleDeletePublicApiButton,
  handleModifyPublicApiButton,
} from '../../AddPublicApiModal/AddPublicApiModal';
import { handleRemoteServerDeleteButton } from '../../AddRemoteServerModal/AddRemoteServerModal';
import {
  DeleteButton,
  handleCrawlerDeleteButton,
  ModifyButton,
} from '../../AddWebcrowler/AddWebcrowler';

// ** [계산] 수집 리스트 제목 **
const calCollectMethodTitle = (value, t) => {
  if (value === 'public_api') return '추가된 API 데이터 목록';
  if (value === 'crawling') return '웹 크롤러 목록';
  if (value === 'remote_server') return '원격 서버 목록';
  if (value === 'flightbase') return '배포 프로젝트 등록';
  return 'ERROR';
};

const calDataForm = (requestValue, formValue) => {
  if (requestValue === 0) return null;
  return formValue ? 'Body' : 'Form';
};

// ** [계산] 리스트 반환 **
const calMethodList = (collectMethodList, collectMethod) => {
  const methodList = collectMethodList[collectMethod];
  if (collectMethod === 'public_api') {
    const dataList = methodList.map((data) => {
      const { info } = data;
      const transfromParams = info.requestParameter.reduce((acc, cur) => {
        acc[cur.key] = cur.value;
        return acc;
      }, {});

      return {
        id: info.apiType === 'public' ? data.id : null,
        name: info.name,
        url: info.apiUrl,
        api_key: info.apiKey,
        providing_organization: info.provider,
        detail_url: info.pageUrl,
        method: info.requestValue ? 'POST' : 'GET',
        data_type: calDataForm(info.requestValue, info.formValue),
        jsonData: transfromParams,
        apiType: info.apiType,
      };
    });
    return dataList;
  }

  if (collectMethod === 'crawling')
    return methodList.map((info) => {
      return {
        name: info.first,
        url: info.second,
      };
    });
  if (collectMethod === 'remote_server') {
    return methodList.map((info) => {
      return {
        name: info.name,
        user: info.user,
        passwd: info.passwd,
        ip: info.ip,
        path: info.path,
      };
    });
  }

  return methodList.map((item) => {
    return {
      id: item.id,
      name: item.first,
      user_name: item.second,
    };
  });
};

// ** [계산] 리스트 목차 반환 **
const calMethodColumnList = (first, second, third, fourth) => {
  return [
    {
      label: first,
      headStyle: {
        flex: '1 144px',
        minWidth: '144px',
        paddingLeft: '16px',
        paddingRight: '16px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 144px',
        minWidth: '144px',
        paddingLeft: '16px',
        paddingRight: '16px',
      },
      cell: ({ first }) => {
        return first;
      },
    },
    {
      label: second,
      headStyle: {
        flex: '1 252px',
        minWidth: '252px',
        paddingRight: '16px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 252px',
        minWidth: '252px',
        paddingRight: '16px',
      },
      cell: ({ second }) => {
        return second;
      },
    },
    {
      label: third,
      headStyle: {
        flex: '1 38px',
        minWidth: '38px',
        paddingRight: '16px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 38px',
        minWidth: '38px',
        paddingRight: '16px',
      },
      cell: ({ third }) => {
        return third;
      },
    },
    {
      label: fourth,
      headStyle: {
        flex: '1 38px',
        minWidth: '38px',
        paddingRight: '16px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 38px',
        minWidth: '38px',
        paddingRight: '16px',
      },
      cell: ({ fourth }) => {
        return fourth;
      },
    },
  ];
};

// ** [계산] column 반환 **
const calCollectMethodColumn = (value) => {
  const columnObj = {
    public_api: {
      first: 'API 이름',
      second: 'API URL',
      third: '수정',
      fourth: '삭제',
    },
    crawling: {
      first: '웹 크롤러 이름',
      second: '웹 크롤러 URL',
      third: '수정',
      fourth: '삭제',
    },
    remote_server: {
      first: '원격 서버 이름',
      second: '원격 서버 IP',
      third: '수정',
      fourth: '삭제',
    },
    flightbase: {
      first: '배포 프로젝트',
      second: '소유자',
      fourth: '삭제',
    },
  };
  const { first, second, third, fourth } = columnObj[value];

  const column = calMethodColumnList(first, second, third, fourth);
  return column;
};

const handleModifyButton = (dispatch, modalType, modalData) => {
  dispatch(
    openModal({
      modalType,
      modalData,
    }),
  );
};

const useCollectMethod = (
  initial,
  initialList,
  workspaceId,
  publicDataList = [],
) => {
  const dispatch = useDispatch();

  const [collectMethod, setCollectMethod] = useState(initial);

  const collectMethodTitle = calCollectMethodTitle(collectMethod);
  const collectMethodColumn = calCollectMethodColumn(collectMethod);

  const [deploymentList, setDeploymentList] = useState([]);

  const calCollectMethodInitialList = (initialList) => {
    const initialValue = {
      public_api: [],
      crawling: [],
      remote_server: [],
      flightbase: [],
    };

    if (!initialList) return initialValue;

    if (collectMethod === 'public_api') {
      initialValue.public_api = initialList.map((info) => {
        const {
          name,
          method,
          providing_organization,
          api_key,
          url,
          data_type,
          detail_url,
          jsonData,
          apiType,
        } = info;

        const requestParameter = jsonData
          ? Object.keys(jsonData).map((key) => {
              return {
                key,
                value: jsonData[key],
              };
            })
          : {};

        return {
          first: name,
          second: url,
          third: (
            <ModifyButton
              handleModifyButton={
                apiType === 'custom'
                  ? () =>
                      handleModifyCustomApiButton(
                        name,
                        url,
                        api_key,
                        providing_organization,
                        detail_url,
                        method === 'GET' ? 0 : 1,
                        data_type,
                        requestParameter,
                        setCollectMethodList,
                        dispatch,
                      )
                  : () => {
                      handleModifyPublicApiButton(
                        requestParameter,
                        info.id,
                        {
                          name,
                          apiUrl: url,
                          provider: providing_organization,
                          pageUrl: detail_url,
                        },
                        method === 'GET' ? 0 : 1,
                        setCollectMethodList,
                        setSelectedApiList,
                        dispatch,
                      );
                    }
              }
            />
          ),
          fourth: (
            <DeleteButton
              handleDeleteButton={
                apiType === 'custom'
                  ? () =>
                      handleDeleteCustomApiButton(
                        name,
                        url,
                        setCollectMethodList,
                      )
                  : () => {
                      handleDeletePublicApiButton(
                        {
                          name,
                          apiUrl: url,
                          provider: providing_organization,
                          pageUrl: detail_url,
                        },
                        setCollectMethodList,
                        setSelectedApiList,
                      );
                    }
              }
            />
          ),
          info: {
            name,
            apiUrl: url,
            api_key,
            provider: providing_organization,
            pageUrl: detail_url,
            requestValue: method === 'GET' ? 0 : 1,
            formValue: data_type,
            requestParameter,
            apiType,
          },
        };
      });
      return initialValue;
    }

    if (collectMethod === 'crawling') {
      initialValue.crawling = initialList.map((info) => {
        const { name, url } = info;
        return {
          first: name,
          second: url,
          third: (
            <ModifyButton
              handleModifyButton={() =>
                handleModifyButton(dispatch, 'ADD_WEB_CROWLER_MODAL', {
                  editName: name,
                  editUrl: url,
                  setCollectMethodList,
                })
              }
            />
          ),
          fourth: (
            <DeleteButton
              handleDeleteButton={() =>
                handleCrawlerDeleteButton(url, name, setCollectMethodList)
              }
            />
          ),
        };
      });
      return initialValue;
    }

    if (collectMethod === 'remote_server') {
      initialValue.remote_server = initialList.map((info) => {
        const { ip, name, passwd, path, user } = info;
        return {
          first: name,
          second: ip,
          third: (
            <ModifyButton
              handleModifyButton={() =>
                handleModifyButton(dispatch, 'ADD_REMOTE_SERVER', {
                  editName: name,
                  editId: user,
                  editPassword: passwd,
                  editIp: ip,
                  editPath: path,
                  setCollectMethodList,
                })
              }
            />
          ),
          fourth: (
            <DeleteButton
              handleDeleteButton={() => {
                handleRemoteServerDeleteButton(name, ip, setCollectMethodList);
              }}
            />
          ),
          ip,
          name,
          passwd,
          path,
          user,
        };
      });
    }

    return initialValue;
  };

  const intialMethodValue = calCollectMethodInitialList(initialList);
  const [collectMethodList, setCollectMethodList] = useState(intialMethodValue);

  useEffect(() => {
    if (!initialList) return;
    if (collectMethod !== 'flightbase') return;

    setCollectMethodList((prev) => {
      const findList = deploymentList.filter((item1) => {
        return initialList.some((item2) => item2.id === item1.id);
      });
      const newList = findList.map((item) => {
        return {
          id: item.id,
          first: item.name,
          second: item.user_name,
          fourth: (
            <DeleteButton
              handleDeleteButton={() =>
                handleFlightbaseDeleteButton(
                  item.name,
                  item.user_name,
                  setCollectMethodList,
                )
              }
            />
          ),
        };
      });
      return {
        ...prev,
        flightbase: newList,
      };
    });
  }, [collectMethod, deploymentList, initialList]);

  useEffect(() => {
    if (collectMethod !== 'public_api') return;
    if (publicDataList.length === 0) return;

    const filterSelectPublicList = publicDataList.filter((item1) => {
      return initialList.some((item2) => item2.id === item1.id);
    });

    setSelectedApiList(filterSelectPublicList);
  }, [collectMethod, initialList, publicDataList]);

  const collect_information_list = calMethodList(
    collectMethodList,
    collectMethod,
  );

  const handleMethod = useCallback((e) => {
    setCollectMethod(e.target.value);
  }, []);

  const handleMethodModal = useCallback(() => {
    const modalTypeObj = {
      public_api: 'ADD_CUSTOM_API_MODAL',
      crawling: 'ADD_WEB_CROWLER_MODAL',
      remote_server: 'ADD_REMOTE_SERVER',
      flightbase: 'ADD_DEPLOY_PROJECT',
    };
    const modalType = modalTypeObj[collectMethod];

    dispatch(
      openModal({
        modalType,
        modalData: {
          collectMethodList,
          setCollectMethodList,
          workspaceId,
        },
      }),
    );
  }, [collectMethod, collectMethodList, dispatch, workspaceId]);

  const [selectedApiList, setSelectedApiList] = useState([]);
  const handlePublicApiSelect = useCallback(
    (itemInfo) => {
      const shallowList = selectedApiList.slice();
      const isValueIndex = shallowList.findIndex(
        (info) => info.id === itemInfo.id,
      );

      if (isValueIndex !== -1) {
        shallowList.splice(isValueIndex, 1);
        setSelectedApiList(shallowList);
        setCollectMethodList((prev) => {
          const shallowList = prev.public_api.slice();
          const isValueIndex = shallowList.findIndex(
            (info) => info.id === itemInfo.id,
          );
          shallowList.splice(isValueIndex, 1);
          return {
            ...prev,
            public_api: shallowList,
          };
        });
      } else {
        dispatch(
          openModal({
            modalType: 'ADD_PUBLIC_API_MODAL',
            modalData: {
              submit: () => {
                setSelectedApiList(() => {
                  const shallowList = selectedApiList.slice();
                  shallowList.push(itemInfo);
                  return shallowList;
                });
                dispatch(closeModal('ADD_PUBLIC_API_MODAL'));
              },
              itemInfo,
              isEdit: false,
              setCollectMethodList,
              setSelectedApiList,
            },
          }),
        );
      }
    },
    [dispatch, selectedApiList],
  );

  return {
    collectMethod,
    collectMethodTitle,
    collectMethodList: collectMethodList[collectMethod],
    collectMethodColumn,
    collect_information_list,
    selectedApiList,
    setDeploymentList,
    handleMethod,
    handleMethodModal,
    handlePublicApiSelect,
  };
};

export default useCollectMethod;
