import { Fragment, useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Icons
import SyncIconWhite from '@src/static/images/icon/00-ic-basic-renew-white.svg';
import SyncIcon from '@src/static/images/icon/00-ic-basic-renew.svg';
import RecordsIcon from '@src/static/images/icon/ic-record-gray.svg';
import MenuIcon from '@src/static/images/icon/00-ic-basic-ellipsis.svg';
import NodeIcon from '@src/static/images/icon/icon-node-gray.svg';
import StorageIcon from '@src/static/images/icon/icon-storage-gray.svg';

// Components
import { Button, Tooltip } from '@jonathan/ui-react';
import PageTitle from '@src/components/atoms/PageTitle';
import DropMenu from '@src/components/molecules/DropMenu';
import BtnMenu from '@src/components/molecules/DropMenu/BtnMenu';
import Tab from '@src/components/molecules/Tab';

// CSS module
import style from './AdminBenchmarkingContent.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function AdminBenchmarkingContent({
  nodeList,
  storageList,
  nodeSyncAll,
  storageSyncAll,
  networkGroupList,
  showNetworkCount,
  nodeResultObj,
  storageResultObj,
  storageDataKeyList,
  nodeRequestCheck,
  storageRequestCheck,
  onSelectNetwork,
  csvDownloadTable,
  openNodeRecordModal,
  openStorageRecordModal,
}) {
  const { t } = useTranslation();
  const targetOptions = [
    { label: t('node.label'), value: 'node', icon: NodeIcon },
    { label: t('storage.label'), value: 'storage', icon: StorageIcon },
  ];
  const [target, setTarget] = useState(targetOptions[0]);

  // 결과 값 가공
  const makeTestValue = (testValue) => {
    if (testValue !== undefined && testValue !== null) {
      if (testValue === 'syncing') {
        testValue = t('syncing.label');
      } else if (
        typeof testValue === 'string' &&
        testValue.toLowerCase().indexOf('error') !== -1
      ) {
        testValue = (
          <div className={cx('error')}>
            <img
              src='/images/icon/error-o.svg'
              alt='error'
              className={cx('error-icon')}
            />
            {testValue}
          </div>
        );
      }
    }
    return testValue;
  };

  return (
    <div id='AdminBenchMarkingContent'>
      <PageTitle>{t('benchmarking.label')}</PageTitle>
      <div className={cx('page-contents')}>
        <Tab
          type='a'
          option={targetOptions}
          select={target}
          tabHandler={setTarget}
        />
        <div className={cx('control-box')}>
          <div className={cx('left-box')}>
            {/* {target.value === 'node' ? '' : ''} */}
          </div>
          <div className={cx('right-box')}>
            {target.value === 'node' && networkGroupList.length > 0 && (
              <div className={cx('filter')}>
                <label>
                  {`${t('network.group.label')} ${t('filter.label')}`}
                </label>
                <div className={cx('select-button')}>
                  <div className={cx('btn-box')}>
                    {networkGroupList.map(({ id, name, selected }) => {
                      return (
                        <div
                          key={id}
                          className={cx('button', selected && 'selected')}
                          onClick={() => {
                            onSelectNetwork(id);
                          }}
                        >
                          {name}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
            <Button
              type='primary-light'
              onClick={() => csvDownloadTable(target.value)}
            >
              CSV {t('download.label')}
            </Button>
          </div>
        </div>
        <div className={cx('table-container')}>
          {target.value === 'node' ? (
            nodeList.filter(
              ({ network_group_name_list: ngnl }) => ngnl.length > 0,
            ).length > 1 ? (
              <table className={cx('benchmark-table', 'node')}>
                <thead>
                  <tr>
                    <th rowSpan={3} colSpan={3}>
                      <div className={cx('button-div')}>
                        <Button
                          type='secondary'
                          size='medium'
                          onClick={() => {
                            nodeRequestCheck(true);
                          }}
                        >
                          <img
                            src={SyncIconWhite}
                            alt={t('syncing.label')}
                            className={cx(
                              'syncing-icon',
                              nodeSyncAll && 'loading',
                            )}
                          />
                          {nodeSyncAll
                            ? t('syncingAll.label')
                            : t('syncAll.label')}
                        </Button>
                      </div>
                    </th>
                    {nodeList.map(
                      ({ id, name, ip, network_group_name_list: ngnl }) => {
                        if (ngnl.length === 0) return false;
                        let columnCount = 0;
                        networkGroupList
                          .filter(({ selected }) => selected)
                          .map(({ id }) => {
                            return (columnCount += ngnl.filter(
                              ({ id: nid }) => id === nid,
                            ).length);
                          });
                        if (networkGroupList.length > 0) {
                          if (
                            networkGroupList.filter(({ selected }) => selected)
                              .length !== 0 &&
                            networkGroupList.filter(({ selected }) => selected)
                              .length < networkGroupList.length
                          ) {
                            if (columnCount === 0) return false;
                          }
                          return (
                            <th colSpan={columnCount} key={id}>
                              <div
                                className={cx('btn')}
                                title={`${name} ${t('sync.label')}`}
                              >
                                <Button
                                  type='none-border'
                                  size='small'
                                  onClick={() => nodeRequestCheck(false, id)}
                                  customStyle={{ padding: '0' }}
                                >
                                  <img
                                    className={cx('sync-icon')}
                                    src={SyncIcon}
                                    alt='sync'
                                  />
                                </Button>
                              </div>
                              <div className={cx('value')} title={`IP: ${ip}`}>
                                {name}
                              </div>
                            </th>
                          );
                        } else {
                          return (
                            <th colSpan={columnCount} key={id}>
                              <div className={cx('value')} title={`IP: ${ip}`}>
                                {name}
                              </div>
                            </th>
                          );
                        }
                      },
                    )}
                  </tr>
                  <tr className={cx('small-row')}>
                    {nodeList.map(
                      ({ network_group_name_list: ngnl }, index) => {
                        if (ngnl.length === 0) return false;
                        const netIdList = ngnl.map(({ id: netId }) => netId);
                        if (showNetworkCount > 0) {
                          return networkGroupList.map(
                            ({ id, name, selected }, i) => {
                              if (selected && netIdList.indexOf(id) !== -1) {
                                const interfaceLength = ngnl.filter(
                                  ({ id: nid }) => id === nid,
                                ).length;
                                return (
                                  <th
                                    key={`${i}-${id}-${name}`}
                                    colSpan={interfaceLength}
                                  >
                                    {name}
                                  </th>
                                );
                              } else {
                                return (
                                  <Fragment
                                    key={`${i}-${id}-${name}`}
                                  ></Fragment>
                                );
                              }
                            },
                          );
                        } else {
                          return (
                            <th
                              key={`empty-${index}`}
                              className={cx('select-network')}
                            >
                              {networkGroupList.length > 0
                                ? t('benchmark.selectNetwork.message')
                                : '-'}
                            </th>
                          );
                        }
                      },
                    )}
                  </tr>
                  <tr className={cx('small-row')}>
                    {nodeList.map(
                      ({ network_group_name_list: ngnl }, index) => {
                        if (ngnl.length === 0) return false;
                        const netIdList = ngnl.map(({ id: netId }) => netId);
                        if (showNetworkCount > 0) {
                          return networkGroupList.map(
                            ({ id, name, selected }, i) => {
                              if (selected) {
                                return ngnl
                                  .filter(({ id: nid }) => id === nid)
                                  .map(({ id, name, interface: port }, j) => {
                                    return (
                                      <th
                                        key={`${i}-${j}-${id}-${name}`}
                                        className={cx(
                                          netIdList.indexOf(id) !== -1
                                            ? 'active'
                                            : 'disabled',
                                        )}
                                      >
                                        {port}
                                      </th>
                                    );
                                  });
                              } else {
                                return (
                                  <Fragment
                                    key={`${i}-${id}-${name}`}
                                  ></Fragment>
                                );
                              }
                            },
                          );
                        } else {
                          return <th key={`empty-${index}`}>-</th>;
                        }
                      },
                    )}
                  </tr>
                </thead>
                <tbody>
                  {nodeList.map(
                    (
                      {
                        id: clientNodeId,
                        name: clientNodeName,
                        ip: clientNodeIp,
                        network_group_name_list: cngnl,
                      },
                      index,
                    ) => {
                      const selectedNetworkGroupId = networkGroupList
                        .filter(({ selected }) => selected)
                        .map(({ id }) => id);
                      const selectedInterfaceClient = cngnl.filter(
                        ({ id: cnid }) =>
                          selectedNetworkGroupId.indexOf(cnid) !== -1,
                      );

                      let firstIndex = 0;
                      let realCount = 0;
                      return networkGroupList
                        .filter(({ selected }) => selected)
                        .map(({ id: networkGroupId }, i) => {
                          const interfaceList = cngnl.filter(
                            ({ id: clientNetworkId }) =>
                              networkGroupId === clientNetworkId,
                          );
                          firstIndex += 1;
                          if (interfaceList.length === 0) {
                            firstIndex += -1;
                          }
                          return interfaceList.map(
                            (
                              {
                                id: clientNetworkGroupId,
                                interface: clientNodeInterface,
                                name: clientNetworkGroupName,
                              },
                              j,
                            ) => {
                              realCount += 1;
                              return (
                                <tr
                                  key={`${index}-${i}-${j}`}
                                  className={cx('small-row')}
                                >
                                  {/* 첫번째 인터페이스를 인지해야함 */}
                                  {firstIndex === 1 && j === 0 && (
                                    <th
                                      id={clientNodeId}
                                      rowSpan={selectedInterfaceClient.length}
                                      title={`IP: ${clientNodeIp}`}
                                    >
                                      {clientNodeName}
                                    </th>
                                  )}
                                  {j / interfaceList.length === 0 && (
                                    <th rowSpan={interfaceList.length} key={i}>
                                      {clientNetworkGroupName}
                                    </th>
                                  )}
                                  <th>{clientNodeInterface}</th>
                                  {nodeList.map(
                                    ({
                                      id: serverNodeId,
                                      name: serverNodeName,
                                      network_group_name_list: sngnl,
                                    }) => {
                                      const selectedNetworkGroupId =
                                        networkGroupList
                                          .filter(({ selected }) => selected)
                                          .map(({ id }) => id);
                                      const selectedInterfaceServer =
                                        sngnl.filter(
                                          ({ id: snid }) =>
                                            selectedNetworkGroupId.indexOf(
                                              snid,
                                            ) !== -1,
                                        );

                                      return selectedInterfaceServer.map(
                                        (
                                          {
                                            id: serverNetworkGroupId,
                                            interface: serverNodeInterface,
                                            name: serverNetworkGroupName,
                                          },
                                          k,
                                        ) => {
                                          if (clientNodeId === serverNodeId) {
                                            if (
                                              firstIndex === 1 &&
                                              j === 0 &&
                                              k === 0
                                            ) {
                                              return (
                                                <td
                                                  key={`${clientNodeId}-${serverNodeId}-same`}
                                                  colSpan={
                                                    selectedInterfaceServer.length
                                                  }
                                                  rowSpan={
                                                    selectedInterfaceClient.length
                                                  }
                                                  className={cx('same-node')}
                                                >
                                                  <span
                                                    className={cx('bar')}
                                                  ></span>
                                                </td>
                                              );
                                            } else {
                                              return (
                                                <Fragment
                                                  key={`${k}-${clientNodeId}-${serverNodeId}-${clientNetworkGroupName}-${serverNetworkGroupName}-${clientNodeInterface}-${serverNodeInterface}-empty`}
                                                ></Fragment>
                                              );
                                            }
                                          }
                                          let testValue =
                                            nodeResultObj[
                                              `${clientNodeId}-${serverNodeId}-${clientNetworkGroupName}-${serverNetworkGroupName}-${clientNodeInterface}-${serverNodeInterface}`
                                            ];
                                          testValue = makeTestValue(testValue);
                                          const idArray = [];
                                          selectedInterfaceClient.forEach(
                                            ({ id }) => {
                                              idArray.push(id);
                                            },
                                          );
                                          selectedInterfaceServer.forEach(
                                            ({ id }) => {
                                              idArray.push(id);
                                            },
                                          );
                                          const idSet = new Set(idArray);
                                          const isDuplicate =
                                            idSet.size < idArray.length;

                                          if (
                                            firstIndex === 1 &&
                                            j === 0 &&
                                            k ===
                                              selectedInterfaceServer.length -
                                                1 &&
                                            isDuplicate
                                          ) {
                                            return (
                                              <td
                                                key={`${index}-${i}-${j}-${k}-btn`}
                                                className={cx(
                                                  'last-right',
                                                  'node-td',
                                                  selectedInterfaceClient.length ===
                                                    realCount && 'last-bottom',
                                                  clientNetworkGroupId ===
                                                    serverNetworkGroupId &&
                                                    'same-network',
                                                )}
                                              >
                                                <div className={cx('btn')}>
                                                  <DropMenu
                                                    btnRender={() => (
                                                      <Button
                                                        type='none-border'
                                                        size='small'
                                                        iconAlign='left'
                                                        icon={MenuIcon}
                                                        iconStyle={{
                                                          margin: '0',
                                                          width: '20px',
                                                          height: '20px',
                                                          filter:
                                                            'brightness(0.4)',
                                                        }}
                                                        customStyle={{
                                                          width: '24px',
                                                          padding: '6px',
                                                        }}
                                                      />
                                                    )}
                                                    menuRender={(
                                                      popupHandler,
                                                    ) => (
                                                      <BtnMenu
                                                        btnList={[
                                                          {
                                                            name: t(
                                                              'sync.label',
                                                            ),
                                                            iconPath: SyncIcon,
                                                            onClick: () =>
                                                              nodeRequestCheck(
                                                                false,
                                                                0,
                                                                {
                                                                  client_node_id:
                                                                    clientNodeId,
                                                                  server_node_id:
                                                                    serverNodeId,
                                                                },
                                                              ),
                                                            disable: false,
                                                          },
                                                          {
                                                            name: t(
                                                              'records.label',
                                                            ),
                                                            iconPath:
                                                              RecordsIcon,
                                                            onClick: () =>
                                                              openNodeRecordModal(
                                                                clientNodeId,
                                                                serverNodeId,
                                                                clientNodeName,
                                                                serverNodeName,
                                                              ),
                                                            disable: false,
                                                          },
                                                        ]}
                                                        callback={popupHandler}
                                                      />
                                                    )}
                                                    align='RIGHT'
                                                  />
                                                </div>
                                                <div>{testValue}</div>
                                              </td>
                                            );
                                          }
                                          return (
                                            <td
                                              key={`${index}-${i}-${j}-${k}-value`}
                                              className={cx(
                                                'node-td',
                                                selectedInterfaceServer.length ===
                                                  k + 1 && 'last-right',
                                                selectedInterfaceClient.length ===
                                                  realCount && 'last-bottom',
                                                clientNetworkGroupId ===
                                                  serverNetworkGroupId &&
                                                  'same-network',
                                              )}
                                            >
                                              {testValue}
                                            </td>
                                          );
                                        },
                                      );
                                    },
                                  )}
                                </tr>
                              );
                            },
                          );
                        });
                    },
                  )}
                </tbody>
              </table>
            ) : (
              <div className={cx('empty-box')}>
                {t('benchmark.node.empty.message')}
              </div>
            )
          ) : storageList.length > 0 ? (
            <table className={cx('benchmark-table', 'storage')}>
              <thead>
                <tr>
                  <th rowSpan={4}>
                    <div className={cx('button-div')}>
                      <Button
                        type='secondary'
                        size='medium'
                        onClick={() => {
                          storageRequestCheck(true);
                        }}
                      >
                        <img
                          src={SyncIconWhite}
                          alt={t('syncing.label')}
                          className={cx(
                            'syncing-icon',
                            storageSyncAll && 'loading',
                          )}
                        />
                        {storageSyncAll
                          ? t('syncingAll.label')
                          : t('syncAll.label')}
                      </Button>
                    </div>
                  </th>
                  {storageList.map(({ id, name, path }) => {
                    return (
                      <th colSpan={8} key={name}>
                        <div
                          className={cx('btn')}
                          title={`${name} ${t('sync.label')}`}
                        >
                          <Button
                            type='none-border'
                            size='small'
                            onClick={() => storageRequestCheck(false, 0, id)}
                            customStyle={{ padding: '0' }}
                          >
                            <img
                              className={cx('sync-icon')}
                              src={SyncIcon}
                              alt='sync'
                            />
                          </Button>
                        </div>
                        <div className={cx('value')} title={`Path: ${path}`}>
                          {name}
                        </div>
                      </th>
                    );
                  })}
                </tr>
                <tr className={cx('small-row')}>
                  {storageList.map(({ name }) => (
                    <Fragment key={name}>
                      <th colSpan={4}>Read</th>
                      <th colSpan={4}>Write</th>
                    </Fragment>
                  ))}
                </tr>
                <tr className={cx('small-row')}>
                  {storageList.map(({ name }) => (
                    <Fragment key={name}>
                      <th colSpan={2}>with buffer</th>
                      <th colSpan={2}>without buffer</th>
                      <th colSpan={2}>with buffer</th>
                      <th colSpan={2}>without buffer</th>
                    </Fragment>
                  ))}
                </tr>
                <tr className={cx('small-row')}>
                  {storageList.map(({ name }, idx) => (
                    <Fragment key={name}>
                      <th>
                        <span>IOPS</span>
                        {idx === 0 && (
                          <Tooltip
                            title='IOPS'
                            contents={t(
                              'benchmark.storage.iops.tooltip.message',
                            )}
                            contentsAlign={{
                              vertical: 'bottom',
                              horizontal: 'left',
                            }}
                            customStyle={{
                              position: 'absolute',
                              top: '-17px',
                            }}
                            iconCustomStyle={{
                              width: '22px',
                            }}
                            contentsCustomStyle={{
                              textAlign: 'left',
                            }}
                          />
                        )}
                      </th>
                      <th>Speed</th>
                      <th>IOPS</th>
                      <th>Speed</th>
                      <th>IOPS</th>
                      <th>Speed</th>
                      <th>IOPS</th>
                      <th>Speed</th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodeList.map(({ id: nodeId, name: nodeName, ip: nodeIp }) => {
                  return (
                    <tr key={nodeName} className={cx('large-row')}>
                      <th>
                        <div
                          className={cx('btn')}
                          title={`${nodeName} ${t('sync.label')}`}
                        >
                          <Button
                            type='none-border'
                            size='small'
                            onClick={() => storageRequestCheck(false, nodeId)}
                            customStyle={{ padding: '0' }}
                          >
                            <img
                              className={cx('sync-icon')}
                              src={SyncIcon}
                              alt='sync'
                            />
                          </Button>
                        </div>
                        <div title={`IP: ${nodeIp}`}>{nodeName}</div>
                      </th>
                      {storageList.map(
                        ({ id: storageId, name: storageName }, idx) => {
                          const btnMenu = (
                            <div className={cx('btn')}>
                              <DropMenu
                                btnRender={() => (
                                  <Button
                                    type='none-border'
                                    size='small'
                                    iconAlign='left'
                                    icon={MenuIcon}
                                    iconStyle={{
                                      margin: '0',
                                      width: '20px',
                                      height: '20px',
                                      filter: 'brightness(0.4)',
                                    }}
                                    customStyle={{
                                      width: '24px',
                                      padding: '6px',
                                    }}
                                  />
                                )}
                                menuRender={(popupHandler) => (
                                  <BtnMenu
                                    btnList={[
                                      {
                                        name: t('sync.label'),
                                        iconPath: SyncIcon,
                                        onClick: () =>
                                          storageRequestCheck(false, 0, 0, {
                                            node_id: nodeId,
                                            storage_id: storageId,
                                          }),
                                        disable: false,
                                      },
                                      {
                                        name: t('records.label'),
                                        iconPath: RecordsIcon,
                                        onClick: () =>
                                          openStorageRecordModal(
                                            nodeId,
                                            storageId,
                                            nodeName,
                                            storageName,
                                          ),
                                        disable: false,
                                      },
                                    ]}
                                    callback={popupHandler}
                                  />
                                )}
                                align='RIGHT'
                              />
                            </div>
                          );
                          if (
                            storageResultObj[`${nodeId}-${storageId}-error`]
                          ) {
                            const testValue = makeTestValue(
                              storageResultObj[`${nodeId}-${storageId}-error`],
                            );
                            return (
                              <td
                                key={`${idx}-${storageId}`}
                                colSpan={8}
                                className={cx('last-right')}
                              >
                                {btnMenu}
                                <div>{testValue}</div>
                              </td>
                            );
                          }
                          return (
                            <Fragment key={`${nodeId}-${storageId}`}>
                              {storageDataKeyList.map((key, idx) => {
                                let testValue =
                                  storageResultObj[
                                    `${nodeId}-${storageId}-${key}`
                                  ];
                                testValue = makeTestValue(testValue);

                                if (idx === storageDataKeyList.length - 1) {
                                  return (
                                    <td
                                      key={`${key}-${storageId}`}
                                      className={cx('last-right')}
                                    >
                                      {btnMenu}
                                      <div>{testValue}</div>
                                    </td>
                                  );
                                }
                                return (
                                  <td key={`${key}-${storageId}`}>
                                    {testValue}
                                  </td>
                                );
                              })}
                            </Fragment>
                          );
                        },
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className={cx('empty-box')}>
              {t('benchmark.storage.empty.message')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminBenchmarkingContent;
