import { Fragment } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useWindowDimensions from '@src/hooks/useWindowDimensions';

// Utils
import { convertBps } from '@src/utils';

// Components
import { Button } from '@jonathan/ui-react';
import ModalFrame from '@src/components/Modal/ModalFrame';
import Loading from '@src/components/atoms/loading/Loading';

// Icons
import ArrowIcon from '@src/static/images/icon/ic-arrow-left-right.svg';
import warningIcon from '@src/static/images/icon/00-ic-alert-warning-yellow.svg';

// CSS module
import classNames from 'classnames/bind';
import style from './BenchmarkStorageRecordModalContent.module.scss';
const cx = classNames.bind(style);

function BenchmarkStorageRecordModalContent({
  type,
  modalData,
  testHistory,
  isLoading,
  csvDownloadRecord,
  onReloadData,
}) {
  const { t } = useTranslation();
  const { width } = useWindowDimensions();

  const { submit, data } = modalData;
  const { nodeName, storageName } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await submit.func;
      return res;
    },
  };

  const storageDataKeyList = [
    'read_withbuffer_iops',
    'read_withbuffer_speed',
    'read_withoutbuffer_iops',
    'read_withoutbuffer_speed',
    'write_withbuffer_iops',
    'write_withbuffer_speed',
    'write_withoutbuffer_iops',
    'write_withoutbuffer_speed',
  ];

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
        <div className={cx('target-name')}>
          <img
            src='/images/nav/icon-lnb-node-gray.svg'
            alt='node'
            className={cx('icon')}
          />
          {nodeName}
          <img src={ArrowIcon} alt='' className={cx('icon', 'arrow')} />
          <img
            src='/images/nav/icon-lnb-storage-gray.svg'
            alt='storage'
            className={cx('icon')}
          />
          {storageName}
        </div>
      </h2>
      <div className={cx('modal-content')}>
        {testHistory ? (
          <Fragment>
            <div className={cx('control-box')}>
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
                    <th className={cx('datetime')} rowSpan={3}>
                      {t('datetime.label')}
                    </th>
                    <th colSpan={4}>Read</th>
                    <th colSpan={4}>Write</th>
                  </tr>
                  <tr className={cx('small-row')}>
                    <th colSpan={2}>with buffer</th>
                    <th colSpan={2}>without buffer</th>
                    <th colSpan={2}>with buffer</th>
                    <th colSpan={2}>without buffer</th>
                  </tr>
                  <tr className={cx('small-row')}>
                    <th>IOPS</th>
                    <th>Speed</th>
                    <th>IOPS</th>
                    <th>Speed</th>
                    <th>IOPS</th>
                    <th>Speed</th>
                    <th>IOPS</th>
                    <th>Speed</th>
                  </tr>
                </thead>
                <tbody>
                  {testHistory &&
                    testHistory.map(({ test_datetime, data }, idx) => {
                      return (
                        <tr key={idx}>
                          <td className={cx('datetime')}>{test_datetime}</td>
                          {data['error_message'] ? (
                            <td key={test_datetime} colSpan={8}>
                              <span className={cx('error')}>
                                <img
                                  src='/images/icon/error-o.svg'
                                  alt='error'
                                />
                                [Error] {data['error_message']}
                              </span>
                            </td>
                          ) : (
                            storageDataKeyList.map((key) => {
                              if (key.indexOf('speed') !== -1) {
                                return (
                                  <td key={key}>
                                    {data[key]
                                      ? convertBps(data[key], 'byte')
                                      : '-'}
                                  </td>
                                );
                              }
                              return <td key={key}>{data[key] ?? '-'}</td>;
                            })
                          )}
                        </tr>
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

export default BenchmarkStorageRecordModalContent;
