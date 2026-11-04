import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { ButtonV2 } from '@jonathan/ui-react';

import AccuracyLossChart from '@src/components/molecules/chart/AccuracyLossChart';

// Actions
import { closeModal } from '@src/store/modules/modal';
import { callApi, network, STATUS_SUCCESS } from '@src/network';

// Components
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

// 스타일
import classNames from 'classnames/bind';
import style from './HpsResultModal.module.scss';

const cx = classNames.bind(style);

function HpsResultModal({ onClose, data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { trainingId } = data;

  const [paramList, setParamList] = useState([]);

  const [fixedParamList, setFixedParamList] = useState([]); // 아직은 필요한 상황 없음

  const [tableData, setTableData] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const [chartData, setChartData] = useState(null);
  const [chartInfo, setChartInfo] = useState(null);

  const [logData, setLogData] = useState([]);
  const [projectName, setProjectName] = useState('');

  const [bestParam, setBestParam] = useState({});
  const [bestValue, setBestValue] = useState({});

  const [sortConfig, setSortConfig] = useState({
    column: '',
    order: 'ASC',
  });

  const handleInitialLoad = useCallback(async () => {
    const response = await callApi({
      url: `projects/hps-result-log?hps_id=${trainingId}`,
      method: 'GET',
    });
    const { status, result, error, message } = response;
    if (status === STATUS_SUCCESS) {
      if (!result || !result.result) return;

      const {
        hps_name,
        parameter,
        result: graphResult,
        best_params,
        best_value,
      } = result;

      setProjectName(hps_name || '');

      // 동적 파라미터(parameter)와 고정 파라미터(fixed_parameter)
      if (parameter) {
        if (Array.isArray(parameter.parameter)) {
          setParamList(parameter.parameter);
        }
        if (Array.isArray(parameter.fixed_parameter)) {
          setFixedParamList(parameter.fixed_parameter);
        }
      }

      setBestParam(best_params);
      setBestValue(best_value);

      // result: [{ id, params, train_logs, source_logs }, ...]
      if (Array.isArray(graphResult)) {
        setTableData(graphResult);
      }
    } else {
      errorToastMessage(error, message);
    }
  }, []);

  // * 정렬 핸들러

  const handleClickSort = useCallback(
    async (colName) => {
      let newOrder = 'ASC';
      if (sortConfig.column === colName && sortConfig.order === 'ASC') {
        newOrder = 'DESC';
      }
      setSortConfig({ column: colName, order: newOrder });
      let newSortKey = '';

      if (colName) {
        newSortKey = colName;
      }
      const response = await callApi({
        url: `projects/hps-result-log?hps_id=${trainingId}&sort_key=${newSortKey}&order_by=${newOrder}`,
        method: 'GET',
      });

      const { result, error, message, status } = response;

      if (status === STATUS_SUCCESS) {
        if (!result || !result.result) return;

        const {
          hps_name,
          parameter,
          result: graphResult,
          best_params,
          best_value,
        } = result;

        setProjectName(hps_name || '');

        // 동적 파라미터(parameter)와 고정 파라미터(fixed_parameter)
        if (parameter) {
          if (Array.isArray(parameter.parameter)) {
            setParamList(parameter.parameter);
          }
          if (Array.isArray(parameter.fixed_parameter)) {
            setFixedParamList(parameter.fixed_parameter);
          }
        }

        setBestParam(best_params);
        setBestValue(best_value);

        // result: [{ id, params, train_logs, source_logs }, ...]
        if (Array.isArray(graphResult)) {
          setTableData(graphResult);
        }
      } else {
        errorToastMessage(error, message);
      }
    },
    [sortConfig.column, sortConfig.order, trainingId],
  );

  // const [bestParams, s]

  const chartRef = useRef(null);

  const newSubmit = {
    text: t('confirm.label'),
    func: async () => {
      dispatch(closeModal('HPS_RESULT_MODAL'));
    },
  };

  // * CSV 다운로드
  const onClickCSVDownload = async () => {
    // CSV 다운로드 or log 다운로드 등

    const { data, status } = await network.callApiWithPromise({
      url: `projects/hps-result-log/download/csv?hps_id=${trainingId}`,
      method: 'get',
    });
    if (status === 200) {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[HPS]CSV.${trainingId}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      errorToastMessage();
    }
  };

  // * LOG 다운로드
  const onClickLogDownload = async () => {
    // CSV 다운로드 or log 다운로드 등

    const { data, status } = await network.callApiWithPromise({
      url: `projects/hps-result-log/download?hps_id=${trainingId}&step=${selectedId}`,
      method: 'get',
    });
    if (status === 200) {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[HPS]Log.${selectedId}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      errorToastMessage();
    }
  };

  useEffect(() => {
    handleInitialLoad();
  }, [handleInitialLoad]);

  const handleRowClick = (rowItem) => {
    const { id, train_logs, source_logs } = rowItem;
    setSelectedId(id);

    //* 1 data
    const metricData = {};
    const keyOrder = [];

    train_logs?.x?.forEach((item) => {
      const { key, values } = item;
      if (key === 'iteration_key') return;
      metricData[key] = values;
      keyOrder.push(key);
    });

    //* 2 info
    const chartInfoObj = {
      key_order: keyOrder,
      x: {
        label: train_logs?.y?.key || 'epoch',
        value: train_logs?.y?.values || [],
      },
      xaxisType: 'numeric',
      yaxisToFixed: 4,
    };

    setChartData(metricData);
    setChartInfo(chartInfoObj);

    //* 3 logs
    setLogData(source_logs || []);

    //* 4 scroll
    setTimeout(() => {
      chartRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest',
      });
    }, 100);
  };

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      // cancel={...}
      isResize
      isMinimize
      type={type}
      title={`[HPS] ${t('trainingResultOf.label', { name: projectName })}`}
      footer
      customStyle={{ minWidth: '1000px' }}
      validate
      footerMessage=''
    >
      {/* 상단 파라미터 박스 */}
      <div className={cx('row')}>
        <div className={cx('title')}>{t('searchParameterSetting.label')}</div>

        <div className={cx('param-box')}>
          {/* 
            1) 동적 파라미터 (parameter.parameter)
               min max 등등 ?
          */}
          {paramList.map((p) => (
            <div className={cx('item')} key={p.name}>
              <span className={cx('param')}>{p.name}</span>
              {/* min */}
              <span className={cx('setting-value')}>
                <span>{t('min.label')}</span>
                <span>{p.min}</span>
              </span>
              {/* max */}
              <span className={cx('setting-value')}>
                <span>{t('max.label')}</span>
                <span>{p.max}</span>
              </span>
              {/* step */}
              <span className={cx('setting-value')}>
                <span>{t('searchCount.label')}</span>
                <span>{p.step}</span>
              </span>
            </div>
          ))}
          {/* {fixedParamList.map((fp) => ( fiexed 파라미터 사용해야할 때 사용용
            <div className={cx('item')} key={fp.name}>
              <span className={cx('param')}>{fp.name}</span>
              <span className={cx('setting-value')}>
                <span>{t('value.label')}</span>
                <span>{fp.value}</span>
              </span>
            </div>
          ))} */}
        </div>
      </div>

      <div className={cx('border')} />

      <div className={cx('score-box')}>
        <div className={cx('title')}>{t('bestScore.label')}</div>
        <div className={cx('best-score')}>
          <span className={cx('score-wrap')}>
            <span className={cx('best-param')}>Target</span>
            <span className={cx('best-param-value')}>
              {bestValue?.value ?? '-'}
            </span>
          </span>

          <span className={cx('target')}>
            {bestParam &&
              Object.entries(bestParam).map(([key, value]) => (
                <span className={cx('score-wrap')} key={key}>
                  <span className={cx('best-param')}>{key}</span>
                  <span className={cx('best-param-value')}>{value}</span>
                </span>
              ))}
          </span>

          {/* <span>
            <span className={cx('param')}>bbb</span>
            <span>cccc</span>
          </span> */}
        </div>
      </div>

      <div className={cx('hps-result-modal')}>
        <div className={cx('title')}>
          {t('searchRecord.label')}
          <ButtonV2
            type='solid'
            size='s'
            colorType='skyblue'
            label={`CSV ${t('download.label')}`}
            onClick={() => onClickCSVDownload()}
          />
        </div>

        {/* 테이블 */}
        <div className={cx('table-section')}>
          <div className={cx('table-wrap')}>
            <table className={cx('table')}>
              <thead>
                <tr>
                  <th style={{ width: '50px' }}>{t('number.label')}</th>
                  {paramList.map((paramInfo) => {
                    const colName = paramInfo.name;
                    const isActiveCol = sortConfig.column === colName;
                    const isDesc = sortConfig.order === 'DESC';

                    return (
                      <th
                        key={colName}
                        onClick={() => handleClickSort(colName)}
                        className={cx('sortable-th', { clicked: isActiveCol })}
                      >
                        <div className={cx('th-content')}>
                          {colName}
                          {isActiveCol ? (
                            <span className={cx(isDesc ? 'desc' : 'asc')}>
                              <span className={cx('arrow')} />
                            </span>
                          ) : (
                            <span className={cx('un-clicked')}>
                              <span className={cx('arrow')} />
                            </span>
                          )}
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {tableData.length > 0 ? (
                  tableData.map((row) => {
                    const { id, params } = row;
                    return (
                      <tr
                        key={id}
                        onClick={() => handleRowClick(row)}
                        style={{
                          backgroundColor:
                            selectedId === id ? '#f0f2f5' : 'transparent',
                          cursor: 'pointer',
                        }}
                      >
                        <td>{id}</td>
                        {paramList.map((p) => (
                          <td key={p.name}>{params[p.name]}</td>
                        ))}
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td
                      colSpan={1 + paramList.length}
                      style={{ textAlign: 'center' }}
                    >
                      No Data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 그래프 & 로그 */}
        <div className={cx('result-log')}>
          <div className={cx('chart')} ref={chartRef}>
            <div className={cx('title')}>
              {selectedId
                ? t('hpsGraph.label', { index: selectedId })
                : t('hpsGraph.label', { index: '- ' })}
            </div>
            {chartData && chartInfo ? (
              <div className={cx('graph')}>
                <AccuracyLossChart
                  data={chartData}
                  info={chartInfo}
                  width={800}
                  height={400}
                  initEmptyMsg='Select a row to see chart'
                />
              </div>
            ) : (
              <div className={cx('no-graph')}>{t('noData.message')}</div>
            )}
          </div>
          <div className={cx('border')} />
          <div className={cx('log')}>
            <div className={cx('title')}>
              {selectedId
                ? t('hpsLog.label', { index: selectedId })
                : t('hpsLog.label', { index: '- ' })}
              <ButtonV2
                type='solid'
                size='s'
                colorType='skyblue'
                label={t('logDownload.label')}
                onClick={onClickLogDownload}
              />
            </div>
            <div className={cx('log-data', logData.length === 0 && 'no-log')}>
              {logData.length > 0
                ? logData.map((logLine, idx) => <p key={idx}>{logLine}</p>)
                : `${t('log.label')} ${t('noData.message')}`}
            </div>
          </div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
}

export default HpsResultModal;
