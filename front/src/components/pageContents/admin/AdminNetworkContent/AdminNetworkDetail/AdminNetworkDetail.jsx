import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// Utils
import { errorToastMessage } from '@src/utils';

// Components
import { Button } from '@jonathan/ui-react';

// CSS module
import style from './AdminNetworkDetail.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const AdminNetworkDetail = ({ data }) => {
  const { t } = useTranslation();
  const {
    id,
    name,
    node_interface_list: nodeInterfaceList,
    cni_info: cniInfo,
  } = data;
  const [testResult, setTestResult] = useState(null);
  const [testStatus, setTestStatus] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const onTest = async () => {
    setIsLoading(true);
    const response = await callApi({
      url: `networks/network-group-check?network_group_id=${id}`,
      method: 'GET',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result.length > 0) {
        setTestStatus('error');
        setTestResult(result);
      } else {
        setTestStatus('success');
        setTestResult(t('network.detail.groupTest.success.message'));
      }
    } else {
      errorToastMessage(error, message);
    }
    setIsLoading(false);
    return response;
  };

  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <h3 className={cx('title')}>{t('detailsOf.label', { name: name })}</h3>
      </div>
      <div className={cx('info')}>
        <div className={cx('first')}>
          <div className={cx('ip-range')}>
            <h3 className={cx('title')}>
              {t('network.detail.groupIpRange.label')}
            </h3>
            <div className={cx('contents')}>
              {cniInfo.ip
                ? `${cniInfo?.ip_range_start} ~ ${cniInfo?.ip_range_end}`
                : '-'}
            </div>
          </div>
          <div className={cx('interface')}>
            <h3 className={cx('title')}>
              {t('network.detail.nodeInterface.label')}
            </h3>
            <div className={cx('contents')}>
              <table className={cx('node-interfaces-table')}>
                <thead>
                  <tr>
                    <th>{t('node.label')}</th>
                    <th>{t('networkInterface.label')}</th>
                  </tr>
                </thead>
                <tbody>
                  {nodeInterfaceList.map(
                    ({ node_name: nodeName, interfaces }) => {
                      return (
                        <tr key={nodeName}>
                          <td>{nodeName}</td>
                          <td>{interfaces.join(', ')}</td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className={cx('second')}>
          <div className={cx('test')}>
            <h3 className={cx('title')}>
              {t('network.detail.groupTest.label')}
            </h3>
            <div className={cx('contents')}>
              <Button
                type='primary-reverse'
                size='small'
                customStyle={{ border: '1px solid #2d76f8' }}
                onClick={() => onTest()}
                loading={isLoading}
              >
                {t('test.label')}
              </Button>
              <>
                {testResult ? (
                  <div className={cx('message', testStatus)}>
                    {testStatus === 'error'
                      ? testResult.map((item, idx) => {
                          const errorForm = `${t(
                            'network.detail.groupTest.error.message',
                          )} `;
                          const nodeForm = item.map(
                            ({ interface: itf, node_name: nodeName }) => {
                              return `${itf} (${nodeName})`;
                            },
                          );
                          return (
                            <p key={idx} className={cx('line-item')}>
                              {errorForm}
                              {nodeForm.join(', ')}
                            </p>
                          );
                        })
                      : testResult}
                  </div>
                ) : (
                  <div className={cx('message')}>
                    {t('network.detail.groupTest.default.message')}
                  </div>
                )}
              </>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminNetworkDetail;
