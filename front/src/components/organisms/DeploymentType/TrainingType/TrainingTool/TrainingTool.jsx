// Images
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import fileImage from '@src/static/images/icon/file-white.svg';

// Components
import SubMenu from '@src/components/molecules/SubMenu';
import LogTable from './LogTable';
import { InputText, Tab } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingTool.module.scss';

const cx = classNames.bind(style);

function TrainingTool({
  jobList,
  trainingToolTab,
  trainingToolTabHandler,
  hpsList,
  toolDetailOpenHandler,
  jobDetailOpenList,
  hpsDetailOpenList,
  toolSelectHandler,
  toolOwnerOptions,
  arrowHandler,
  selectedTool,
  hpsLogTable,
  selectedHpsScore,
  selectedToolType,
  toolSortHandler,
  toolSearchValue,
  toolSelectedOwner,
  hpsLogSortHandler,
  selectedHpsId,
  selectedLogId,
  logClickHandler,
  toolModelSearchValue,
  toolModelSortHandler,
  hpsModelList,
  jobModelList,
  hpsModelSelectValue,
  jobModelSelectValue,
  toolModelSelectHandler,
  trainingTypeArrow,
  trainingTypeArrowHandler,
  editStatus,
  userName,
  readOnly,
  t,
}) {
  const category = [
    {
      label: `JOB (${jobList?.length || '0'})`,
      component: () => (
        <div key={1}>
          {jobList?.length > 0 ? (
            jobList.map((v, i) => {
              return (
                <div key={i}>
                  <div
                    className={cx(
                      'tool-box',
                      v?.checkpoint_count === 0 && 'disabled',
                    )}
                    onClick={() => toolDetailOpenHandler(i, 'job')}
                  >
                    <div className={cx('name')}>{v.job_name}</div>
                    <div className={cx('owner')}>{v.job_runner_name}</div>
                    <div className={cx('date')}>{v.job_create_datetime}</div>
                    <div className={cx('tool-arrow')}>
                      <img src={arrowDown} alt='arrow' />
                    </div>
                  </div>
                  {jobDetailOpenList[i]?.arrow && (
                    <div className={cx('detail-contents')}>
                      <div>
                        {v.job_group_list?.map((detail, idx) => {
                          return (
                            <div
                              key={idx}
                              className={cx(
                                'detail-container',
                                detail?.checkpoint_count === 0
                                  ? 'detail-disable'
                                  : '',
                              )}
                              onClick={() => {
                                toolSelectHandler({
                                  type: 'JOB',
                                  name: v.job_name,
                                  jobId: detail.job_id,
                                  jobIdx: detail.job_group_name,
                                  detailNumber: v.job_group_list.length - idx,
                                  jobCheckpoint: detail.checkpoint_list,
                                });
                              }}
                            >
                              <div className={cx('detail-box')}>
                                <div className={cx('title-number')}>
                                  <span>JOB {detail.job_group_name + 1}</span>
                                </div>
                                {detail.run_parameter?.map((v, i) => {
                                  return (
                                    <div className={cx('detail-data')} key={i}>
                                      <span>{v.key}</span>
                                      <span>{v.value}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className={cx('empty-tool')}>{t('noJOB.message')}</div>
          )}
        </div>
      ),
    },
    {
      label: `HPS (${hpsList?.length || '0'})`,
      component: () => (
        <div key={2}>
          {hpsList?.length > 0 ? (
            hpsList.map((v, i) => {
              return (
                <div key={i}>
                  <div
                    className={cx(
                      'tool-box',
                      v?.checkpoint_count === 0 && 'disabled',
                    )}
                    onClick={() => toolDetailOpenHandler(i, 'hps')}
                  >
                    <div className={cx('name')}>{v.hps_name}</div>
                    <div className={cx('owner')}>{v.hps_runner_name}</div>
                    <div className={cx('date')}>{v.hps_create_datetime}</div>
                    <div className={cx('tool-arrow')}>
                      <img src={arrowDown} alt='arrow' />
                    </div>
                  </div>
                  {hpsDetailOpenList[i]?.arrow && (
                    <div className={cx('detail-contents')}>
                      <div>
                        {v.hps_group_list?.map((detail, idx) => {
                          return (
                            <div
                              key={idx}
                              className={cx(
                                'detail-container',
                                detail?.checkpoint_count === 0
                                  ? 'detail-disable'
                                  : '',
                              )}
                              onClick={() => {
                                toolSelectHandler({
                                  type: 'HPS',
                                  name: v.hps_name,
                                  detailNumber: detail.hps_group_name + 1,
                                  hpsIdx: detail.hps_group_name,
                                  hpsLogTable: detail.hps_number_info,
                                  hpsCheckpoint:
                                    detail.hps_number_info.max_item
                                      .checkpoint_list,
                                });
                              }}
                            >
                              <div className={cx('detail-box')}>
                                <div className={cx('title-number')}>
                                  <span>HPS {detail.hps_group_name + 1}</span>
                                </div>
                                {detail.run_parameter?.map((v, i) => {
                                  return (
                                    <div className={cx('detail-data')} key={i}>
                                      <span>{v.key}</span>
                                      <span>{v.value}</span>
                                    </div>
                                  );
                                })}
                                {detail.search_parameter?.map((v, i) => {
                                  return (
                                    <div className={cx('detail-data')} key={i}>
                                      <span>{v.key}</span>
                                      <span>{v.value}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className={cx('empty-tool')}>{t('noHPS.message')}</div>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <div
        className={cx(
          'tab',
          !trainingTypeArrow.tool && 'close',
          readOnly ? 'readOnly' : 'editable',
        )}
        onClick={() => {
          if (!editStatus) {
            trainingTypeArrowHandler('tool');
          }
        }}
      >
        <div className={cx('title')}>
          {t('deploymentTypeTraining.tool.label')}
        </div>
        <div className={cx('content', selectedTool && 'selected-content')}>
          {selectedTool ? selectedTool : t('deploymentToolSelect.label')}
        </div>
        <div className={cx('arrow-train')}>
          <img src={trainingTypeArrow.tool ? arrowUp : arrowDown} alt='arrow' />
        </div>
      </div>

      {trainingTypeArrow.tool && (
        <>
          <div className={cx('train-content')}>
            <div className={cx('input')}>
              <InputText
                value={toolSearchValue}
                onChange={(e) =>
                  toolSortHandler({
                    e,
                    type: trainingToolTab === 0 ? 'job' : 'hps',
                  })
                }
                disableLeftIcon={false}
                placeholder={t('name.label')}
              />
            </div>
            {userName !== 'root' && (
              <div className={cx('button-box')}>
                <div className={cx('button')}>
                  <span className={cx('type-title')}>{t('owner.label')}</span>
                  <SubMenu
                    option={toolOwnerOptions}
                    select={toolSelectedOwner}
                    onChangeHandler={(e) => {
                      toolSortHandler({ selectedItem: e });
                    }}
                    customStyle={{ marginBottom: 0, marginRight: 0 }}
                    size={'small'}
                  />
                </div>
              </div>
            )}
          </div>
          <div className={cx('container')}>
            <Tab
              selectedItem={trainingToolTab}
              onClick={(tab) => trainingToolTabHandler(tab)}
              category={category}
              renderComponent={category[trainingToolTab].component}
              isScroll={false}
              isScrollCorrection={false}
              customStyle={{
                label: {
                  display: 'flex',
                  alignItems: 'center',
                  width: '100px',
                  height: '36px',
                },
                tab: {
                  backgroundColor: '#fff',
                },
                selectBtnArea: {
                  backgroundColor: '#fff',
                },
                component: {
                  paddingBottom: '8px',
                  background: 'transparent',
                },
              }}
              t={t}
            />
          </div>
        </>
      )}
      {selectedToolType === 'job' && trainingToolTab === 0 && (
        <>
          <div
            className={cx(
              'model-box',
              !trainingTypeArrow.jobModel && 'closed',
              readOnly ? 'readOnly' : 'editable',
            )}
            onClick={() => {
              if (!editStatus) {
                trainingTypeArrowHandler('jobModel');
              }
            }}
          >
            <div className={cx('title')}>{t('Model')}</div>
            <div className={cx('input-wrap')}>
              <div
                className={cx(
                  'selected-model',
                  jobModelSelectValue !== '' ? 'select' : 'no-select',
                )}
              >
                {jobModelSelectValue !== ''
                  ? jobModelSelectValue
                  : t('deploymentModelSelect.label')}
              </div>
              <div className={cx('arrow-model')}>
                <img
                  src={trainingTypeArrow.jobModel ? arrowUp : arrowDown}
                  alt='arrow'
                />
              </div>
            </div>
          </div>
          {trainingTypeArrow.jobModel && (
            <>
              <div className={cx('model-search')}>
                <InputText
                  value={toolModelSearchValue}
                  onChange={(e) => toolModelSortHandler({ e, tool: 'job' })}
                  disableLeftIcon={false}
                  placeholder={t('name.label')}
                />
              </div>
              <div className={cx('model-list')}>
                {jobModelList?.length > 0 ? (
                  <>
                    {jobModelList.map((v, i) => {
                      return (
                        <div
                          className={cx('list-wrap')}
                          onClick={() => toolModelSelectHandler(v, 'job')}
                          key={i}
                        >
                          <div className={cx('img')}>
                            <img src={fileImage} alt='file' />
                          </div>
                          <div className={cx('value')}>{v}</div>
                        </div>
                      );
                    })}
                  </>
                ) : (
                  <div className={cx('empty')}>{t('noData.message')}</div>
                )}
              </div>
            </>
          )}
        </>
      )}
      {selectedToolType === 'hps' && trainingToolTab === 1 && (
        <>
          <LogTable
            hpsLogTable={hpsLogTable}
            selectedHpsScore={selectedHpsScore}
            arrowHandler={arrowHandler}
            trainingTypeArrowHandler={trainingTypeArrowHandler}
            trainingToolTab={trainingToolTab}
            hpsLogSortHandler={hpsLogSortHandler}
            selectedHpsId={selectedHpsId}
            selectedLogId={selectedLogId}
            logClickHandler={logClickHandler}
            trainingTypeArrow={trainingTypeArrow}
            editStatus={editStatus}
            t={t}
            readOnly={readOnly}
          />
          {(selectedLogId === 0 || selectedLogId) && (
            <>
              <div
                className={cx(
                  'model-box',
                  !trainingTypeArrow.hpsModel && 'closed',
                  readOnly ? 'readOnly' : 'editable',
                )}
                onClick={() => {
                  if (!editStatus) {
                    trainingTypeArrowHandler('hpsModel');
                  }
                }}
              >
                <div className={cx('title')}>{t('Model')}</div>
                <div className={cx('input-wrap')}>
                  <div
                    className={cx(
                      'selected-model',
                      hpsModelSelectValue !== '' ? 'select' : 'no-select',
                    )}
                  >
                    {hpsModelSelectValue !== ''
                      ? hpsModelSelectValue
                      : t('deploymentModelSelect.label')}
                  </div>
                  <div className={cx('arrow-model')}>
                    <img
                      src={trainingTypeArrow.hpsModel ? arrowUp : arrowDown}
                      alt='arrow'
                    />
                  </div>
                </div>
              </div>
              {trainingTypeArrow.hpsModel && (
                <>
                  <div className={cx('model-search')}>
                    <InputText
                      value={toolModelSearchValue}
                      onChange={(e) => toolModelSortHandler({ e, tool: 'hps' })}
                      disableLeftIcon={false}
                      placeholder={t('name.label')}
                    />
                  </div>
                  <div className={cx('model-list')}>
                    {hpsModelList?.length > 0 ? (
                      <>
                        {hpsModelList.map((v, i) => {
                          return (
                            <div
                              className={cx('list-wrap')}
                              onClick={() => toolModelSelectHandler(v, 'hps')}
                              key={i}
                            >
                              <div className={cx('img')}>
                                <img src={fileImage} alt='file' />
                              </div>
                              <div className={cx('value')}>{v}</div>
                            </div>
                          );
                        })}
                      </>
                    ) : (
                      <div className={cx('empty')}>{t('noData.message')}</div>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
export default TrainingTool;
