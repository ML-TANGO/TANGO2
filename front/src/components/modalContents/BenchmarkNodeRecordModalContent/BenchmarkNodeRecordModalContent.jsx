import { Fragment } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useWindowDimensions from '@src/hooks/useWindowDimensions';

// Components
import { Button } from '@jonathan/ui-react';
import ModalFrame from '@src/components/Modal/ModalFrame';
import Loading from '@src/components/atoms/loading/Loading';

// Icons
import ArrowIcon from '@src/static/images/icon/ic-arrow-left-right.svg';
import warningIcon from '@src/static/images/icon/00-ic-alert-warning-yellow.svg';

// Utils
import { convertBps } from '@src/utils';
import { convertLocalTime } from '@src/datetimeUtils';

// CSS module
import classNames from 'classnames/bind';
import style from './BenchmarkNodeRecordModalContent.module.scss';
const cx = classNames.bind(style);

function BenchmarkNodeRecordModalContent({
  type,
  modalData,
  testHistory,
  isLoading,
  networkGroupList,
  selectedNetworkInfo,
  onSelectNetwork,
  csvDownloadRecord,
  onReloadData,
}) {
  const { t } = useTranslation();
  const { width } = useWindowDimensions();

  const { submit, data } = modalData;
  const { clientNodeName, serverNodeName } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await submit.func;
      return res;
    },
  };

  return (
    <ModalFrame
      submit={newSubmit}
      type={type}
      validate={true}
      isResize={true}
      isMinimize={true}
      title={`${t('benchmarking.label')} ${t('records.label')}`}
      customStyle={{
        width: width > 1920 ? '1800px' : width > 1200 ? '1200px' : '780px',
      }}
    >
      <h2 className={cx('title')}>
        {`${t('benchmarking.label')} ${t('records.label')}`}
        <div className={cx('node-name')}>
          <img
            src='/images/nav/icon-lnb-node-gray.svg'
            alt='node'
            className={cx('icon')}
          />
          {serverNodeName}
          <img src={ArrowIcon} alt='' className={cx('icon', 'arrow')} />
          <img
            src='/images/nav/icon-lnb-node-gray.svg'
            alt='node'
            className={cx('icon')}
          />
          {clientNodeName}
        </div>
      </h2>
      <div className={cx('modal-content')}>
        {testHistory ? (
          <Fragment>
            <div className={cx('summary-box')}>
              <div className={cx('group-box')}>
                {networkGroupList.map(
                  ({ idx, name, selected, network_group_index: index }) => {
                    return (
                      <div
                        key={idx}
                        className={cx('button', selected && 'selected')}
                        onClick={() => {
                          onSelectNetwork(idx);
                        }}
                      >
                        {name}
                        {index && <span className={cx('index')}>{index}</span>}
                      </div>
                    );
                  },
                )}
              </div>
              <div className={cx('info-box')}>
                {selectedNetworkInfo && (
                  <Fragment>
                    <div className={cx('interface')}>
                      [{selectedNetworkInfo.name}]{' '}
                      {selectedNetworkInfo.server_node_interface}
                      <img src={ArrowIcon} alt='' className={cx('icon')} />
                      {selectedNetworkInfo.client_node_interface}
                    </div>
                    <div className={cx('bandwidth-box')}>
                      <div className={cx('item', 'max')}>
                        <label>{t('maxBandwidth.label')}</label>
                        <div className={cx('bandwidth')}>
                          {selectedNetworkInfo.bandwidth_overview
                            .maximum_bandwidth
                            ? convertBps(
                                selectedNetworkInfo.bandwidth_overview
                                  .maximum_bandwidth,
                              )
                            : '-'}
                        </div>
                        <div className={cx('datetime')}>
                          {selectedNetworkInfo.bandwidth_overview
                            .maximum_start_datetime
                            ? convertLocalTime(
                                selectedNetworkInfo.bandwidth_overview
                                  .maximum_start_datetime,
                              )
                            : ''}
                        </div>
                      </div>
                      <div className={cx('item', 'min')}>
                        <label>{t('minBandwidth.label')}</label>
                        <div className={cx('bandwidth')}>
                          {selectedNetworkInfo.bandwidth_overview
                            .minimum_bandwidth
                            ? convertBps(
                                selectedNetworkInfo.bandwidth_overview
                                  .minimum_bandwidth,
                              )
                            : '-'}
                        </div>
                        <div className={cx('datetime')}>
                          {selectedNetworkInfo.bandwidth_overview
                            .minimum_start_datetime
                            ? convertLocalTime(
                                selectedNetworkInfo.bandwidth_overview
                                  .minimum_start_datetime,
                              )
                            : ''}
                        </div>
                      </div>
                      <div className={cx('item', 'avg')}>
                        <label>{t('avgBandwidth.label')}</label>
                        <div className={cx('bandwidth')}>
                          {selectedNetworkInfo.bandwidth_overview.avg_bandwidth
                            ? convertBps(
                                selectedNetworkInfo.bandwidth_overview
                                  .avg_bandwidth,
                              )
                            : '-'}
                        </div>
                      </div>
                    </div>
                  </Fragment>
                )}
              </div>
            </div>
            <div className={cx('btn-box')}>
              <Button
                type='primary-light'
                size='small'
                onClick={csvDownloadRecord}
              >
                CSV {t('download.label')}
              </Button>
            </div>
            <div className={cx('table-container')}>
              <table className={cx('benchmark-history-table')}>
                <thead>
                  <tr>
                    <th className={cx('datetime')}>{t('datetime.label')}</th>
                    <th className={cx('network')}>{t('network.label')}</th>
                    <th>
                      {t('serverNodeInterface.label', { node: serverNodeName })}
                    </th>
                    <th>
                      {t('clientNodeInterface.label', { node: clientNodeName })}
                    </th>
                    <th className={cx('bandwidth')}>
                      {t('network.speed.label')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {testHistory.map((data) => {
                    return data.map(
                      (
                        {
                          start_datetime: time,
                          network_group_id: networkGroupId,
                          network_group_name: networkGroupName,
                          network_group_index: networkGroupIndex,
                          server_node_interface: serverNodeInterface,
                          client_node_interface: clientNodeInterface,
                          bandwidth,
                          error_message: errorMessage,
                        },
                        idx,
                      ) => {
                        const isSelected =
                          selectedNetworkInfo.id === networkGroupId &&
                          selectedNetworkInfo.network_group_index ===
                            networkGroupIndex;
                        const isMaxItem =
                          time ===
                            selectedNetworkInfo.bandwidth_overview
                              .maximum_start_datetime &&
                          networkGroupId === selectedNetworkInfo.id &&
                          networkGroupIndex ===
                            selectedNetworkInfo.network_group_index;

                        const isMinItem =
                          time ===
                            selectedNetworkInfo.bandwidth_overview
                              .minimum_start_datetime &&
                          networkGroupId === selectedNetworkInfo.id &&
                          networkGroupIndex ===
                            selectedNetworkInfo.network_group_index;

                        return (
                          <tr
                            key={idx}
                            className={cx(
                              isSelected && 'selected',
                              isMaxItem && 'max',
                              isMinItem && 'min',
                            )}
                          >
                            {idx === 0 && (
                              <td
                                className={cx('datetime')}
                                rowSpan={data.length}
                              >
                                {convertLocalTime(time)}
                              </td>
                            )}
                            <td className={cx('network')}>
                              {networkGroupName}
                              {networkGroupIndex && (
                                <span className={cx('index')}>
                                  {networkGroupIndex}
                                </span>
                              )}
                            </td>
                            <td className={cx('interface')}>
                              {serverNodeInterface}
                            </td>
                            <td className={cx('interface')}>
                              {clientNodeInterface}
                            </td>
                            <td className={cx('bandwidth')}>
                              {(bandwidth && (
                                <span className={cx('bandwidth-value')}>
                                  {convertBps(bandwidth)}
                                </span>
                              )) ||
                                (errorMessage && (
                                  <span className={cx('error')}>
                                    <img
                                      src='/images/icon/error-o.svg'
                                      alt='error'
                                    />
                                    [Error] {errorMessage}
                                  </span>
                                ))}
                            </td>
                          </tr>
                        );
                      },
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Fragment>
        ) : (
          <div className={cx('no-data-box')}>
            {isLoading ? (
              <Loading />
            ) : (
              <Fragment>
                <img src={warningIcon} alt='!' className={cx('icon')} />
                <div className={cx('message')}>
                  {t('benchmark.noCellData.message')}
                </div>
                <Button
                  type='primary-reverse'
                  size='large'
                  onClick={onReloadData}
                >
                  {t('benchmark.reload.label')}
                </Button>
              </Fragment>
            )}
          </div>
        )}
      </div>
    </ModalFrame>
  );
}

export default BenchmarkNodeRecordModalContent;
