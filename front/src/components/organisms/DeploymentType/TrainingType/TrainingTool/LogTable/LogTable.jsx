import { useState, useEffect } from 'react';

// Images
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';

// Utils
import { intCheck } from '@src/utils';

// Components
import { Badge } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './LogTable.module.scss';

const cx = classNames.bind(style);
let clickedList = {};

function LogTable({
  hpsLogTable,
  selectedHpsScore,
  hpsLogSortHandler,
  selectedHpsId,
  selectedLogId,
  logClickHandler,
  trainingTypeArrow,
  trainingTypeArrowHandler,
  editStatus,
  readOnly,
  t,
}) {
  const [clicked, setClicked] = useState({ id: 1, target: 0 });
  const [clickedTitle, setClickedTitle] = useState({ id: 1, target: 0 });

  const searchParamKeys =
    hpsLogTable?.log_table?.length > 0
      ? Object.keys(hpsLogTable?.log_table[0].params)
      : [];

  const paramKeysList = Object.assign(
    {},
    ...searchParamKeys?.map((key) => ({ [key]: 0 })),
  );
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

    let sortBy = clicked[title] ? 'DESC' : 'ASC';

    const isParam =
      searchParamKeys.filter((param) => param === title).length > 0 ? 1 : 0;

    hpsLogSortHandler({ title, sortBy, isParam, id: selectedHpsId });
  };

  useEffect(() => {
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

  return (
    <div className={cx('hps-box')}>
      <div
        className={cx(
          'hps-input-box',
          !trainingTypeArrow.hps && 'closed',
          readOnly ? 'readOnly' : 'editable',
        )}
        onClick={() => {
          if (!editStatus) {
            trainingTypeArrowHandler('hps');
          }
        }}
        style={{
          borderBottom: `${!trainingTypeArrow.hps ? 'none' : ''}`,
        }}
      >
        <div className={cx('title')}>{t('hpsNo.label')}</div>
        <div className={cx('hps-info')}>
          <div className={cx('hps-no')}>
            {selectedLogId}
            {selectedLogId === hpsLogTable?.max_item?.id && (
              <Badge
                customStyle={{ marginLeft: '4px' }}
                label='Best'
                type='green'
              />
            )}
          </div>
          <div className={cx('arrow-train')}>
            <img
              src={trainingTypeArrow.hps ? arrowUp : arrowDown}
              alt='arrow'
            />
          </div>
        </div>
      </div>
      {trainingTypeArrow.hps && (
        <div className={cx('result-table')}>
          <table className={cx('table')}>
            <thead>
              <tr>
                <th className={cx('id')}>
                  <div
                    className={cx('id-wrap')}
                    onClick={() => clickTitleHandler('id')}
                  >
                    <div className={cx('number')}>{t('number.label')}</div>
                    <span
                      className={cx(
                        `${clickedTitle['id'] ? 'clicked' : 'un-clicked'}`,
                      )}
                    >
                      <span
                        className={cx(
                          `${
                            clickedTitle['id'] && clicked['id'] ? 'desc' : 'asc'
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
                        `${clickedTitle['target'] ? 'clicked' : 'un-clicked'}`,
                      )}
                      onClick={() => clickTitleHandler('target')}
                    >
                      {t('score.label')}
                      <span
                        className={cx(
                          `${
                            clickedTitle['target'] && clicked['target']
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
                  searchParamKeys?.map((key, i) => (
                    <th key={i}>
                      <span>
                        <span
                          className={cx(
                            `${clickedTitle[key] ? 'clicked' : 'un-clicked'}`,
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
            <tbody className={cx('tbody-wrap')}>
              {hpsLogTable?.log_table?.map((tableData, logIndex) => {
                const {
                  id,
                  target,
                  params,
                  hps_id: hpsId,
                  checkpoint_list: checkpointList,
                  checkpoint_count: checkpoint,
                } = tableData;

                return (
                  <tr
                    key={logIndex}
                    onClick={() => {
                      logClickHandler({
                        id,
                        hpsId,
                        target,
                        tableData,
                        checkpoint,
                        checkpointList,
                      });
                    }}
                    className={cx(
                      selectedLogId === id && 'selected',
                      checkpoint === 0 && 'disabled',
                    )}
                  >
                    <td className={cx('id')}>{id}</td>
                    <td className={cx('target')}>
                      {hpsLogTable?.max_item?.id === id && (
                        <Badge
                          customStyle={{ marginRight: '4px' }}
                          label='Best'
                          type='green'
                        />
                      )}
                      {!(logIndex === hpsLogTable?.log_table.length)
                        ? target !== null
                          ? intCheck(target)
                            ? target
                            : target.toFixed(2)
                          : '-'
                        : null}
                    </td>
                    {params &&
                      Object.keys(params).map((key, i) => (
                        <td key={i} title={params[`${key}`]}>
                          {params[`${key}`] !== null
                            ? intCheck(params[`${key}`])
                              ? params[`${key}`]
                              : params[`${key}`].toFixed(4)
                            : '-'}
                        </td>
                      ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default LogTable;
