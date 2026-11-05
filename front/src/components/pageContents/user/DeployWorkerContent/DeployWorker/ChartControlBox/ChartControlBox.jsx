import { useMemo, useEffect, useState, useRef, useCallback } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import DeployLogDownloadBtn from '@src/components/molecules/DeployLogDownloadBtn/DeployLogDownloadBtn';
import { Button, Selectbox, Tooltip } from '@jonathan/ui-react';
import ChartControlBoxModal from './ChartControlBoxModal/ChartControlBoxModal';

// Icon
import download from '@src/static/images/icon/00-ic-data-download-blue.svg';

// Utils
import { formatSecondsTime } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './ChartControlBox.module.scss';
const cx = classNames.bind(style);

function ChartControlBox({
  workerList,
  selectedGraph,
  infoData = {
    call: {
      total: 0,
      min: 0,
      max: 0,
    },
    abnormal: {
      total: {
        count: 0,
        max_count: 0,
        rate: 0,
        max_rate: 0,
      },
      nginx: {
        count: 0,
        max_count: 0,
        rate: 0,
        max_rate: 0,
      },
      api: {
        count: 0,
        max_count: 0,
        rate: 0,
        max_rate: 0,
      },
    },
    processing_time: {
      average: 0,
      min: 0,
      max: 0,
      max_timestamp: 0,
      median: 0,
      90: 0,
      99: 0,
      95: 0,
    },
    response_time: {
      average: 0,
      min: 0,
      max: 0,
      max_timestamp: 0,
      median: 0,
      90: 0,
      99: 0,
      95: 0,
    },
  },
  onSelectGraph,
  abnormalOptions,
  selectedAbnormal,
  selectInputHandler,
  logDownOptions,
  logDownOptionsHandler,
  processTimeResponseTimeList,
  selectedGraphPer,
  checkOptions,
  onSelectProcessTime,
  onSelectResponseType,
  onDownloadCallLogs,
  optionClickHandler,
}) {
  const { t } = useTranslation();
  const modalRef = useRef();
  const processSelectRef = useRef(null);
  const responseSelectRef = useRef(null);

  const {
    call,
    abnormal,
    processing_time: processingTime,
    response_time: responseTime,
  } = infoData;

  const clickList = useMemo(
    () => ({
      abnormal: false,
      processing: false,
      response: false,
    }),
    [],
  );

  const [clicked, setClicked] = useState(clickList);
  const [borderColor, setBorderColor] = useState('#BDC0C4');

  /**
   * 모달 바깥 클릭 시 모달 닫는 함수
   * @param {object} target
   */
  const handleClickOutside = useCallback(
    ({ target }) => {
      if (clicked && !modalRef.current?.contains(target)) {
        setClicked(clickList);
      }
    },
    [clickList, clicked],
  );

  /**
   * 어떤 버튼을 클릭했는지 체크하는 함수
   * @param {object} e
   * @param {string} title
   */
  const clickHandler = (e, title) => {
    e.stopPropagation();
    setClicked({ ...clickList, [title]: !clicked[title] });
  };

  /**
   * 모달 리스트 클릭 핸들러
   * @param {object} option
   */
  const listClickHandler = (name, value) => {
    setClicked({ ...clickList, [name]: !clicked[name] });
    selectInputHandler(name, value);
  };

  useEffect(() => {
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, [handleClickOutside]);

  useEffect(() => {
    if (!checkOptions.nginx && !checkOptions.api) {
      setBorderColor('#eb3e2a');
    } else if (checkOptions.nginx && checkOptions.api) {
      setBorderColor('#BDC0C4');
    } else {
      setBorderColor('#2D76F8');
    }
  }, [checkOptions]);

  return (
    <div>
      <div className={cx('chart-info')}>
        <div
          className={cx(
            'contents',
            selectedGraph && selectedGraph.callCnt && 'selected',
          )}
          onClick={() => {
            onSelectGraph('Call Count');
          }}
        >
          <div className={cx('label-box')}>
            <label className={cx('label', 'call')}>
              {t('callCount.label')}
            </label>
          </div>
          <span>
            {call?.total > 10000
              ? `${(call?.total / 1000).toFixed(1)}K`
              : call?.total || 0}
          </span>
          <span>
            Max :{' '}
            {call?.max > 10000
              ? ` ${(call?.max / 1000).toFixed(1)}K`
              : call?.max || ' 0'}
          </span>
        </div>
        <div
          className={cx(
            'contents',
            selectedGraph && selectedGraph.abProcess && 'selected',
          )}
          onClick={() => {
            onSelectGraph('Abnormal Process');
          }}
        >
          <div className={cx('label-box')}>
            <label className={cx('label')}>
              {t('abnormalProcessing.label')}
            </label>
            <div ref={modalRef}>
              <Button
                type='gray'
                customStyle={{
                  backgroundColor: `${
                    !checkOptions.nginx && !checkOptions.api
                      ? '#ffe6e5'
                      : '#ffffff'
                  }`,
                  width: '100px',
                  borderColor: borderColor,
                  justifyContent: 'space-between',
                  paddingLeft: '14px',
                  cursor: 'default',
                }}
                icon={'/images/icon/ic-down.svg'}
                iconAlign='right'
                onClick={(e) => clickHandler(e, 'abnormal')}
                iconStyle={{
                  width: '16px',
                  height: '16px',
                  transform: `${clicked.abnormal ? 'rotate(180deg)' : ''}`,
                }}
              >
                {t(selectedAbnormal.label)}
              </Button>
              {clicked.abnormal && (
                <ChartControlBoxModal
                  options={abnormalOptions}
                  listClickHandler={listClickHandler}
                  clickedTitle='abnormal'
                  hasCheckbox={true}
                  checkboxClickHandler={optionClickHandler}
                  checkboxOptions={checkOptions}
                  t={t}
                />
              )}
            </div>
            <Tooltip
              contents={
                <>
                  <div>{t('abnormalProcessing.tooltip.message1')}</div>
                  <div>{t('abnormalProcessing.tooltip.message2')}</div>
                </>
              }
              contentsAlign={{ vertical: 'top', horizontal: 'right' }}
              iconCustomStyle={{
                width: '20px',
                marginLeft: '2px',
              }}
            />
          </div>
          <span>{abnormal?.total?.[selectedAbnormal.value] || 0}</span>
          <span>
            Max : {abnormal?.total?.['max_' + selectedAbnormal.value] || 0}
          </span>
        </div>
        <div
          className={cx(
            'contents',
            selectedGraph && selectedGraph.processTime && 'selected',
          )}
          onClick={(e) => {
            if (
              processSelectRef.current &&
              !processSelectRef.current.contains(e.target)
            ) {
              onSelectGraph('Process Time');
            }
          }}
        >
          <div className={cx('label-box')}>
            <label className={cx('label')}>{t('processingTime.label')}</label>
            <div ref={processSelectRef}>
              <Selectbox
                size='medium'
                list={processTimeResponseTimeList}
                selectedItem={
                  processTimeResponseTimeList[
                    selectedGraphPer.processTime.value
                  ]
                }
                customStyle={{
                  selectboxForm: {
                    width: '130px',
                    color: '#747474',
                  },
                  listForm: {
                    width: '130px',
                  },
                }}
                onChange={(type, _, e) => {
                  e.preventDefault();
                  onSelectProcessTime(type);
                }}
                t={t}
              />
            </div>
            <Tooltip
              contents={t('processingTime.tooltip.message')}
              contentsAlign={{ vertical: 'top', horizontal: 'right' }}
              iconCustomStyle={{
                width: '20px',
                marginLeft: '2px',
              }}
            />
          </div>
          <span>
            {processingTime
              ? formatSecondsTime((processingTime?.[selectedGraphPer.processTime.selected]))
              : '0ms'
            }
          </span>
          <span>Max : {processingTime?.max ? formatSecondsTime((processingTime.max)) : '0ms'}</span>
        </div>
        <div
          className={cx(
            'contents',
            selectedGraph && selectedGraph.response && 'selected',
          )}
          onClick={(e) => {
            if (
              responseSelectRef.current &&
              !responseSelectRef.current.contains(e.target)
            ) {
              onSelectGraph('Response Time');
            }
          }}
        >
          <div className={cx('label-box')}>
            <label className={cx('label')}>{t('responseTime.label')}</label>
            <div ref={responseSelectRef}>
              <Selectbox
                size='medium'
                list={processTimeResponseTimeList}
                selectedItem={
                  processTimeResponseTimeList[
                    selectedGraphPer.responseTime.value
                  ]
                }
                customStyle={{
                  selectboxForm: {
                    width: '130px',
                    color: '#747474',
                  },
                  listForm: {
                    width: '130px',
                  },
                }}
                onChange={onSelectResponseType}
                t={t}
              />
            </div>
            <Tooltip
              contents={t('responseTime.tooltip.message')}
              contentsAlign={{ vertical: 'top', horizontal: 'right' }}
              iconCustomStyle={{
                width: '20px',
                marginLeft: '2px',
              }}
            />
          </div>
          <span>
            {responseTime? formatSecondsTime(responseTime?.[selectedGraphPer.responseTime.selected]) : '0ms'}
          </span>
          <span>Max : {responseTime?.max ? formatSecondsTime(responseTime.max) : '0ms'}</span>
        </div>
      </div>
      <div className={cx('select-chart')}>
        <div className={cx('btn-box')}>
          <div
            className={cx(
              'button',
              selectedGraph && selectedGraph.cpu && 'selected',
            )}
            onClick={() => {
              onSelectGraph('CPU');
            }}
          >
            CPU
          </div>
          <div
            className={cx(
              'button',
              selectedGraph && selectedGraph.ram && 'selected',
            )}
            onClick={() => {
              onSelectGraph('RAM');
            }}
          >
            RAM
          </div>
          <div
            className={cx(
              'button',
              selectedGraph && selectedGraph.gpuCore && 'selected',
            )}
            onClick={() => {
              onSelectGraph('GPU Core');
            }}
          >
            GPU Core
          </div>
          <div
            className={cx(
              'button',
              selectedGraph && selectedGraph.gpuMem && 'selected',
            )}
            onClick={() => {
              onSelectGraph('GPU MEM');
            }}
          >
            GPU MEM
          </div>
          {workerList && (
            <div
              className={cx(
                'button',
                selectedGraph && selectedGraph.worker && 'selected',
              )}
              onClick={() => {
                onSelectGraph('Worker');
              }}
            >
              {t('worker.label')}
            </div>
          )}
        </div>
        <DeployLogDownloadBtn
          btnRender={() => (
            <Button type='primary-reverse' icon={download} iconAlign='right'>
              {t('callLogsDownload.label')}
            </Button>
          )}
          logDownOptions={logDownOptions}
          logDownOptionsHandler={logDownOptionsHandler}
          logDownClickHandler={onDownloadCallLogs}
          tooltipAlign={{ vertical: 'top', horizontal: 'right' }}
        />
      </div>
    </div>
  );
}

export default ChartControlBox;
