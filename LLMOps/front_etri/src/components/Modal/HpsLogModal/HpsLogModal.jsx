import { Badge, Button, Tooltip } from '@tango/ui-react';

// Icon
import download from '@src/static/images/icon/00-ic-data-download-white.svg';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import CircleLoading from '@src/components/atoms/loading/CircleLoading';
import Loading from '@src/components/atoms/loading/Loading';
import Status from '@src/components/atoms/Status';
import AccuracyLossChart from '@src/components/molecules/chart/AccuracyLossChart';
import EmptyBox from '@src/components/molecules/EmptyBox';
import { toast } from '@src/components/Toast';

// Custom Hooks
import useWindowDimensions from '@src/hooks/useWindowDimensions';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage, intCheck, scrollTo } from '@src/utils';

// Components
import ModalFrame from '../ModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './HpsLogModal.module.scss';

const cx = classNames.bind(style);

let prevHpsId;
let clickedList;

const HpsLogModal = ({
  validate,
  data,
  type,
  logTable,
  selectedLogId,
  logData,
  totalLength,
  hpsName,
  hpsData,
  hpsStatus,
  selectHPS,
  maxJobIndex,
  maxJobInfo,
  downloadLog,
  metricsData,
  metricsInfo,
  parameterSettings,
  selectedHps,
  onSubmit,
  loading,
  noGraphData,
}) => {
  const { t } = useTranslation();
  const { submit, trainingName } = data;
  const [clicked, setClicked] = useState(null);
  const [clickedTitle, setClickedTitle] = useState(clickedList);
  const [newTableData, setNewTableData] = useState(logTable);
  const [newMaxJobIndex, setNewMaxJobIndex] = useState(maxJobIndex);
  const [clickedBestRecord, setClickedBestRecord] = useState({
    newMaxJobIndex: false,
  });
  const scrollRef = useRef();
  const resultBoxRef = useRef();
  const targetScrollRef = useRef();
  const scrollToTarget = () => {
    const targetY =
      scrollRef.current.offsetHeight - resultBoxRef.current.offsetHeight;
    scrollTo(scrollRef.current, targetY, 600);
  };
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };
  const paramKeys = parameterSettings.map(({ key }) => key);

  const searchParamKeys =
    logTable?.length > 0 && Object.keys(logTable[0].params);

  const paramKeysList = Object.assign(
    {},
    ...paramKeys.map((key) => ({ [key]: 0 })),
  );

  const scrollHandler = () => {
    const targetY = scrollRef.current.offsetHeight - 400;
    scrollTo(scrollRef.current, targetY, 600);

    setTimeout(() => {
      targetScrollRef.current?.scrollTo(0, newMaxJobIndex * 40, 600);
      setClickedBestRecord({
        [newMaxJobIndex]: true,
      });
    }, 200);
  };

  useEffect(() => {
    setNewTableData(logTable);
  }, [logTable]);

  useEffect(() => {
    setNewMaxJobIndex(maxJobIndex);
  }, [maxJobIndex]);

  // key 할당
  useEffect(() => {
    prevHpsId = undefined;
    clickedList = {
      id: 1,
      target: 0,
      ...paramKeysList,
    };
    setClickedTitle({
      ...clickedList,
    });
    setClicked({
      ...clickedList,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const clickTitleHandler = async (title) => {
    const newClickList = {
      id: 0,
      target: 0,
      ...paramKeysList,
      [title]: 1,
    };
    setClickedTitle(newClickList);
    if (!clickedTitle[title]) {
      setClicked(newClickList);
    } else {
      const newClicked = {
        id: 0,
        target: 0,
        ...paramKeysList,
        [title]: !clicked[title],
      };
      setClicked(newClicked);
    }

    const { hps_id } = maxJobInfo;
    let sortBy = clicked[title] ? 'DESC' : 'ASC';
    const isParam =
      searchParamKeys.filter((param) => param === title).length > 0 ? 1 : 0;
    const response = await callApi({
      url: `projects/hyperparam_search_result?hps_id=${hps_id}&sort_key=${title}&order_by=${sortBy}&is_param=${isParam}`,
      method: 'get',
    });
    const { status, message, result, error } = response;
    if (status === STATUS_SUCCESS) {
      setNewTableData(result.log_table);
      setNewMaxJobIndex(result?.max_index);
    } else {
      errorToastMessage(error, message);
    }
  };

  const handleCsvDownload = useCallback(
    async (hpsData, hpsName) => {
      const { id: hps_id } = hpsData;

      try {
        const { data: csvData } = await network.callApiWithPromise({
          url: `projects/hps-log-table-download?hps_id=${hps_id}`,
          method: 'GET',
        });

        const { self_response } = csvData;
        const { body } = self_response;

        const url = window.URL.createObjectURL(new Blob([body]));
        const link = document.createElement('a');
        link.href = url;
        link.download = `[HPS]${hpsName}-search-result-table.csv`;
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } catch (error) {
        toast.error(t('downloadError'));
        console.log('[ERROR CSV DOWNLOAD] : ', error);
      }
    },
    [t],
  );

  let scoreParamKeys = [];
  if (maxJobInfo) scoreParamKeys = Object.keys(maxJobInfo.params);
  const { width } = useWindowDimensions();

  const logTableIndex = useMemo(() => {
    if (logTable.length === 0 || !selectedHps) return '';
    return logTable[selectedHps.index].id;
  }, [logTable, selectedHps]);

  return (
    <ModalFrame
      submit={newSubmit}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={`[${trainingName}] ${t('hpsResultOf.label', {
        name: `${hpsName}${logTableIndex && `-${logTableIndex}`}`,
      })}`}
      customStyle={{
        width: width > 1920 ? '1800px' : width > 1200 ? '1200px' : '780px',
      }}
    >
      <h2 className={cx('title')}>
        <Status status={hpsStatus} />
        {`[${trainingName}] ${t('hpsResultOf.label', {
          name: `${hpsName}${logTableIndex && `-${logTableIndex}`}`,
        })}`}
      </h2>
      <div className={cx('form')} ref={scrollRef}>
        <div className={cx('parameter-box')}>
          <h3 className={cx('sub-title')}>{t('parameterSettings.label')}</h3>
          <div className={cx('parameter')}>
            {parameterSettings.length > 0
              ? parameterSettings.map(({ key, value }, idx) => (
                  <div key={idx}>
                    <label className={cx('label')}>{key}</label>
                    <span className={cx('value')}>{value}</span>
                  </div>
                ))
              : '-'}
          </div>
        </div>
        <div className={cx('result')}>
          <div className={cx('result-score')}>
            <h3 className={cx('sub-title')}>
              {t('bestScore.label')}
              <Tooltip contents={t('bestScoreInfo.label')} />
            </h3>
            <div className={cx('score-info-box')}>
              <div className={cx('score-info-item')}>
                <p className={cx('label')}>Target</p>
                {maxJobInfo?.target ? (
                  <span
                    className={cx('value')}
                    onClick={(e) => scrollHandler(e)}
                  >
                    {maxJobInfo?.target}
                  </span>
                ) : (
                  '-'
                )}
              </div>
              <div className={cx('score-info-item')}>
                <p className={cx('label')}>Parameters</p>
                <div className={cx('param-box')}>
                  {scoreParamKeys.length === 0
                    ? '-'
                    : scoreParamKeys.map((key) => (
                        <div key={key} className={cx('param-item')}>
                          <label className={cx('param-key')}>{key}</label>
                          <span className={cx('param-value')}>
                            {maxJobInfo?.params[key]}
                          </span>
                        </div>
                      ))}
                </div>
              </div>
            </div>
          </div>

          <div className={cx('table-log-wrap')}>
            <div className={cx('result-table')}>
              <div className={cx('research-title')}>
                <h3 className={cx('sub-title')}>{t('searchRecord.label')}</h3>
                <Button
                  type='secondary'
                  icon={download}
                  iconAlign='right'
                  onClick={() => handleCsvDownload(hpsData, hpsName)}
                >
                  CSV {t('download.label')}
                </Button>
              </div>
              {loading ? (
                <div className={cx('loading-wrap')}>
                  <Loading />
                </div>
              ) : (
                <div className={cx('table-wrap')} ref={targetScrollRef}>
                  {logTable?.length === 0 ? (
                    <EmptyBox
                      customStyle={{ height: '120px' }}
                      text={'noData.message'}
                      isBox
                    />
                  ) : (
                    <table className={cx('table')}>
                      <thead>
                        <tr>
                          <th className={cx('id')}>
                            <div
                              className={cx('id-wrap')}
                              onClick={() => clickTitleHandler('id')}
                            >
                              <div className={cx('test')}>
                                {t('number.label')}
                              </div>
                              <span
                                className={cx(
                                  `${
                                    clickedTitle['id']
                                      ? 'clicked'
                                      : 'un-clicked'
                                  }`,
                                )}
                              >
                                <span
                                  className={cx(
                                    `${
                                      clickedTitle['id'] && clicked['id']
                                        ? 'desc'
                                        : 'asc'
                                    }`,
                                  )}
                                >
                                  <span className={cx('arrow')}></span>
                                </span>
                              </span>
                            </div>
                          </th>
                          <th className={cx('target')}>
                            <span className={cx('target-wrap')}>
                              <span
                                className={cx(
                                  `${
                                    clickedTitle['target']
                                      ? 'clicked'
                                      : 'un-clicked'
                                  }`,
                                )}
                                onClick={() => clickTitleHandler('target')}
                              >
                                {t('score.label')}
                                <span
                                  className={cx(
                                    `${
                                      clickedTitle['target'] &&
                                      clicked['target']
                                        ? 'desc'
                                        : 'asc'
                                    }`,
                                  )}
                                >
                                  <span className={cx('arrow')}></span>
                                </span>
                              </span>
                            </span>
                          </th>
                          {searchParamKeys &&
                            searchParamKeys.map((key) => (
                              <th key={key}>
                                <span>
                                  <span
                                    className={cx(
                                      `${
                                        clickedTitle[key]
                                          ? 'clicked'
                                          : 'un-clicked'
                                      }`,
                                    )}
                                  >
                                    <span
                                      className={cx(
                                        `${
                                          clickedTitle[key] && clicked[key]
                                            ? 'desc'
                                            : 'asc'
                                        }`,
                                      )}
                                      onClick={() => clickTitleHandler(key)}
                                    >
                                      {key}
                                      <span className={cx('arrow')}></span>
                                    </span>
                                  </span>
                                </span>
                              </th>
                            ))}
                        </tr>
                      </thead>

                      <tbody>
                        {newTableData?.map(
                          (
                            { id, target, params, datetime, hps_id: hpsId },
                            logIndex,
                          ) => {
                            return (
                              <tr
                                key={id}
                                onClick={() => {
                                  selectHPS(
                                    { id, index: logIndex },
                                    scrollToTarget,
                                  );
                                  setClickedBestRecord({
                                    [newMaxJobIndex]: false,
                                  });
                                }}
                                className={cx(
                                  selectedLogId === id &&
                                    clickedBestRecord[logIndex] &&
                                    'selected',
                                  newMaxJobIndex === logIndex && 'max-value',
                                  (() => {
                                    if (
                                      prevHpsId !== undefined &&
                                      hpsId !== prevHpsId &&
                                      logIndex !== 0
                                    ) {
                                      prevHpsId = hpsId;
                                      return 'init';
                                    }
                                    prevHpsId = hpsId;
                                    return '';
                                  })(),
                                  datetime &&
                                    !datetime.elapsed &&
                                    logIndex !== 0 &&
                                    'init',
                                  logIndex === newMaxJobIndex &&
                                    clickedBestRecord[logIndex] &&
                                    'search-record',
                                )}
                              >
                                <td className={cx('id')}>{id}</td>
                                <td className={cx('target')}>
                                  {hpsStatus === 'running' &&
                                    logIndex === logTable.length - 1 && (
                                      <CircleLoading />
                                    )}
                                  {newMaxJobIndex === logIndex && (
                                    <Badge
                                      customStyle={{ marginRight: '4px' }}
                                      label={'Best'}
                                      type='green'
                                    />
                                  )}
                                  {!(
                                    hpsStatus === 'running' &&
                                    logIndex === logTable.length - 1
                                  )
                                    ? target !== null
                                      ? intCheck(target)
                                        ? target
                                        : target.toFixed(4)
                                      : '-'
                                    : null}
                                </td>
                                {params &&
                                  Object.keys(params).map((key) => (
                                    <td key={key} title={params[`${key}`]}>
                                      {params[`${key}`] !== null
                                        ? intCheck(params[`${key}`])
                                          ? params[`${key}`]
                                          : params[`${key}`].toFixed(4)
                                        : '-'}
                                    </td>
                                  ))}
                              </tr>
                            );
                          },
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
            <div className={cx('result-log')}>
              <div className={cx('chart')}>
                <h3 className={cx('sub-title')} ref={resultBoxRef}>
                  {logTableIndex
                    ? t('hpsGraph.label', {
                        index: logTableIndex,
                      })
                    : t('hpsGraph.label', {
                        index: '- ',
                      })}
                </h3>
                <AccuracyLossChart
                  data={metricsData}
                  info={metricsInfo}
                  width={width > 1920 ? 1712 : width > 1200 ? 1112 : 698}
                  height={400}
                  initEmptyMsg={
                    noGraphData ? 'noData.message' : 'selectStage.message'
                  }
                />
              </div>
              <div className={cx('log')}>
                <h3 className={cx('sub-title')}>
                  {logTableIndex
                    ? t('hpsLog.label', {
                        index: logTableIndex,
                      })
                    : t('hpsLog.label', {
                        index: '- ',
                      })}
                </h3>
                <div className={cx('download')}>
                  <Button
                    type='secondary'
                    icon={download}
                    iconAlign='right'
                    onClick={() => downloadLog(hpsData.index + 1)}
                    disabled={selectedLogId === null}
                  >
                    {t('logDownload.label')}
                  </Button>
                </div>
              </div>
              {!logData || logData.length === 0 ? (
                <EmptyBox
                  customStyle={{ height: '120px' }}
                  text={logData ? 'noData.message' : 'selectStage.message'}
                  isBox
                />
              ) : (
                <div className={cx('row')}>
                  {(() => {
                    const arr = [];
                    for (let i = 0; i < logData.length; i += 1) {
                      if (totalLength > 200 && i === 100) {
                        arr.push(
                          <p key='ellipsis' className={cx('ellipsis')}>
                            .<br />.<br />.<br />
                          </p>,
                        );
                      }
                      if (logData[i].length === 0) {
                        arr.push(<br key={i} />);
                      } else {
                        arr.push(<p key={i}>{logData[i]}</p>);
                      }
                    }
                    return arr;
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ModalFrame>
  );
};

export default HpsLogModal;
