// Images
import { useState } from 'react';

// Components
import { Badge, Button, InputText } from '@tango/ui-react';

import InfiniteScrollDropDown from '@src/components/molecules/InfiniteScrollDropDown';
import SubMenu from '@src/components/molecules/SubMenu';

// import SkeletonLine from '@src/components/atoms/SkeletonLine/SkeletonLine';
import CustomBottom from './CustomBottom';
import TrainingTool from './TrainingTool';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingType.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import plusImage from '@src/static/images/icon/00-ic-basic-plus-blue.svg';
// import fileImage from '@src/static/images/icon/file-white.svg';
import deleteImage from '@src/static/images/icon/delete-gray.svg';
import builtInImage from '@src/static/images/icon/ic-built-in-blue.svg';
import customImage from '@src/static/images/icon/ic-custom-blue.svg';

const cx = classNames.bind(style);

function TrainingType({
  type,
  trainingList,
  trainingSelectedType,
  trainingSelectedOwner,
  trainingTypeSelectHandler,
  trainingSearch,
  trainingInputValue,
  trainingSortHandler,
  getJobList,
  tabClickHandler,
  getJobs,
  jobDetailList, // Object
  jobDetailOpenList, // Array
  toolDetailOpenHandler,
  jobList,
  hpsList,
  hpsDetailList,
  hpsDetailOpenList,
  trainingToolTab,
  trainingToolTabHandler,
  selectedTraining,
  selectedTool,
  selectedToolType,
  toolSelectHandler,
  trainingSelectHandler,
  trainingType,
  getCustomList,
  paramsInputHandler,
  customFile,
  customParam,
  customRuncode,
  runcodeClickHandler,
  variablesAdd,
  variablesDelete,
  variablesValues,
  variableInputHandler,
  variablesSortHandler,
  customSearchValue,
  customLan,
  hpsLogTable,
  selectedHpsScore,
  selectedHps,
  customList,
  toolSortHandler,
  toolSearchValue,
  toolSelectedOwner,
  customListStatus,
  hpsLogSortHandler,
  selectedTrainingData,
  selectedHpsId,
  selectedLogId,
  logClickHandler,
  toolModelSearchValue,
  toolModelSortHandler,
  hpsModelList,
  jobModelList,
  jobModelSelectValue,
  hpsModelSelectValue,
  toolModelSelectHandler,
  trainingTypeArrow,
  trainingTypeArrowHandler,
  editStatus,
  readOnly,
  t,
  resetCustomInputAndEnvironments,
}) {
  const userName = sessionStorage.getItem('user_name');
  const typeMenuOptions = [
    { label: 'all.label', value: 'all' },
    { label: 'Custom', value: 'custom' },
    // { label: 'Built-in', value: 'builtIn' },
  ];
  const ownerMenuOptions = [
    { label: 'all.label', value: 'allOwner' },
    { label: 'owner', value: 'owner' },
  ];
  const toolOwnerOptions = [
    { label: 'all.label', value: 'toolAll' },
    { label: 'owner', value: 'toolOwner' },
  ];
  const [trainingId, setTrainingId] = useState(0);

  return (
    <div
      className={cx(
        'training-box',
        trainingTypeArrow.train ||
          (!trainingTypeArrow.train && !selectedTraining)
          ? 'open'
          : 'close',
      )}
    >
      <div
        className={cx(
          'tab',
          !trainingTypeArrow.train && 'close',
          readOnly ? 'readOnly' : 'editable',
          !selectedTraining && 'no-selected',
        )}
        onClick={() => {
          if (!editStatus) {
            trainingTypeArrowHandler('train');
          }
        }}
      >
        <div className={cx('title')}>{t('project.label')}</div>
        <div className={cx('content', selectedTraining && 'selected-content')}>
          {selectedTraining
            ? selectedTraining
            : t('deploymentTrainingSelect.label')}
        </div>
        <div className={cx('arrow-train')}>
          <img
            src={trainingTypeArrow.train ? arrowUp : arrowDown}
            alt='arrow'
          />
        </div>
      </div>
      {trainingTypeArrow.train && (
        <>
          <div className={cx('train-content')}>
            <div className={cx('input')}>
              <InputText
                value={trainingInputValue}
                onChange={(e) => trainingSortHandler({ e })}
                disableLeftIcon={false}
                placeholder={t('deploymentInputNameDesc.placeholder')}
              />
            </div>
            <div className={cx('button-box', userName === 'root' && 'admin')}>
              {userName !== 'root' && (
                <div className={cx('button')}>
                  <span className={cx('type-title')}>{t('owner.label')}</span>
                  <SubMenu
                    option={ownerMenuOptions}
                    select={trainingSelectedOwner}
                    onChangeHandler={(e) => {
                      trainingSortHandler({ selectedItem: e });
                    }}
                    customStyle={{ marginBottom: 0, marginRight: 0 }}
                    size={'small'}
                  />
                </div>
              )}
            </div>
          </div>
          <div className={cx('train-list')}>
            {trainingList?.trained_training_list &&
            trainingList?.trained_training_list.length > 0 ? (
              trainingList.trained_training_list.map((list, idx) => {
                return (
                  <div
                    className={cx(
                      'list-box',
                      selectedTraining === list.training_name &&
                        'selected-train',
                    )}
                    key={idx}
                    onClick={() => {
                      // trainingTypeArrowHandler('train');
                      if (selectedTraining !== list.training_name) {
                        resetCustomInputAndEnvironments(list);
                        getJobList(list, list.training_name);
                        if (
                          list.training_type === 'advanced' ||
                          list.training_type === 'custom'
                        ) {
                          console.log('list is change');
                          getCustomList(list);
                          setTrainingId(list.training_id);
                        }
                      }
                    }}
                  >
                    <div className={cx('image-icon')}></div>
                    <div className={cx('name-box')}>
                      <div className={cx('name-desc')}>
                        <span className={cx('name')}>{list.training_name}</span>
                        <span
                          className={cx(
                            'desc',
                            `${
                              selectedTraining === list.training_name &&
                              'selected'
                            }`,
                          )}
                        >
                          {list.training_type === 'built-in'
                            ? list.built_model_name
                            : list.training_description}
                        </span>
                        {selectedTraining === list.training_name && (
                          <div className={cx('name-icon')}></div>
                        )}
                      </div>
                    </div>
                    <div
                      className={cx(
                        'owner',
                        `${
                          selectedTraining === list.training_name && 'selected'
                        }`,
                      )}
                    >
                      {list.training_user_name}
                    </div>
                    <div
                      className={cx(
                        list.training_bookmark === 1
                          ? 'bookmark'
                          : 'empty-bookmark',
                      )}
                      name={t('bookmark.label')}
                    ></div>
                  </div>
                );
              })
            ) : (
              <div className={cx('empty')}>{t('noData.message')}</div>
            )}
          </div>
        </>
      )}
      {selectedTraining && trainingType === 'built-in' && (
        <TrainingTool
          type={type}
          trainingToolTab={trainingToolTab}
          trainingToolTabHandler={trainingToolTabHandler}
          hpsList={hpsList}
          jobList={jobList}
          toolDetailOpenHandler={toolDetailOpenHandler}
          jobDetailOpenList={jobDetailOpenList}
          jobDetailList={jobDetailList}
          toolSelectHandler={toolSelectHandler}
          hpsDetailOpenList={hpsDetailOpenList}
          hpsDetailList={hpsDetailList}
          trainingType={trainingType}
          trainingInputValue={trainingInputValue}
          trainingSortHandler={trainingSortHandler}
          toolOwnerOptions={toolOwnerOptions}
          trainingSelectedOwner={trainingSelectedOwner}
          selectedTool={selectedTool}
          selectedToolType={selectedToolType}
          customParam={customParam}
          customFile={customFile}
          paramsInputHandler={paramsInputHandler}
          runcodeClickHandler={runcodeClickHandler}
          getJobs={getJobs}
          hpsLogTable={hpsLogTable}
          selectedHpsScore={selectedHpsScore}
          selectedHps={selectedHps}
          toolSortHandler={toolSortHandler}
          toolSearchValue={toolSearchValue}
          toolSelectedOwner={toolSelectedOwner}
          customListStatus={customListStatus}
          hpsLogSortHandler={hpsLogSortHandler}
          selectedHpsId={selectedHpsId}
          selectedLogId={selectedLogId}
          logClickHandler={logClickHandler}
          selectedTrainingData={selectedTrainingData}
          toolModelSearchValue={toolModelSearchValue}
          toolModelSortHandler={toolModelSortHandler}
          hpsModelList={hpsModelList}
          jobModelList={jobModelList}
          jobModelSelectValue={jobModelSelectValue}
          hpsModelSelectValue={hpsModelSelectValue}
          toolModelSelectHandler={toolModelSelectHandler}
          trainingTypeArrow={trainingTypeArrow}
          editStatus={editStatus}
          trainingTypeArrowHandler={trainingTypeArrowHandler}
          userName={userName}
          t={t}
          readOnly={readOnly}
        />
      )}
      {selectedTraining &&
        (trainingType === 'advanced' || trainingType === 'custom') && (
          <>
            <div
              className={cx(
                'custom-search-box',
                readOnly ? 'readOnly' : 'editable',
              )}
              onClick={() => {
                if (!editStatus) {
                  trainingTypeArrowHandler('variable');
                }
              }}
            >
              <div className={cx('search-title')}>
                {t('deploymentTypeRunCommand.label')}
              </div>
              <div className={cx('input-box')}>
                <div className={cx('row')}>
                  <div
                    className={cx('first-input')}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type='text'
                      value={customLan}
                      onChange={(e) => paramsInputHandler({ e, type: 'lan' })}
                      placeholder={t('deploymentInputPackage.placeholder')}
                      readOnly={editStatus}
                      className={cx('lang-input')}
                    />
                  </div>
                  <div
                    className={cx('second-input')}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className={cx('custom-file-input')}>
                      <InfiniteScrollDropDown
                        placeholder={t('runCode.placeholder')}
                        handleSelectOption={(selectItem) => {
                          runcodeClickHandler({ name: selectItem.value });
                        }}
                        value={{
                          label: customFile ?? '',
                          value: customFile ?? '',
                        }}
                        tid={Number(trainingId)}
                        listCustomStyle={{
                          maxHeight: '110px',
                          overflow: 'auto',
                        }}
                        isCloseBorder={false}
                      />
                    </div>

                    {/* <input
                      className={cx(
                        'custom-file-input',
                        `${trainingTypeArrow.variable ? 'focus' : 'normal'}`,
                      )}
                      value={customFile}
                      readOnly={true}
                    /> */}
                    {/* <div className={cx('image')}>
                      <img
                        className={cx('img')}
                        src={trainingTypeArrow.variable ? arrowUp : arrowDown}
                        alt='type'
                        onClick={() => {
                          if (!editStatus) {
                            trainingTypeArrowHandler('variable');
                          }
                        }}
                      />
                    </div> */}
                    {/* {trainingTypeArrow.variable && (
                      <div className={cx('custom-file-list')}>
                        {customList &&
                          customList.map((file, index) => (
                            <div
                              onClick={() => {
                                runcodeClickHandler({ name: file });
                                trainingTypeArrowHandler('variable');
                              }}
                              key={file}
                              className={cx(
                                'file',
                                `${
                                  file === customFile ? 'selected' : 'normal'
                                }`,
                              )}
                            >
                              <div
                                className={cx(
                                  `${
                                    file === customFile
                                      ? 'selected-icon'
                                      : 'normal-icon'
                                  }`,
                                )}
                              ></div>
                              <span>{file.slice(0, 50)}</span>
                            </div>
                          ))}
                      </div>
                    )} */}
                    {/* <div className={cx('custom-mid')}>
                      <div className={cx('custom-input')}>
                        <InputText
                          value={customSearchValue}
                          onChange={(e) => variablesSortHandler({ e })}
                          disableLeftIcon={false}
                          options={{ width: '100%' }}
                          customStyle={{ width: '100%' }}
                          placeholder={t('deploymentInputNameDesc.placeholder')}
                          isDisabled={editStatus}
                        />
                      </div>
                    </div> */}
                  </div>
                </div>
                <div className={cx('row')}>
                  <div
                    className={cx('third-input')}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type='text'
                      value={customParam}
                      onChange={(e) => paramsInputHandler({ e, type: 'param' })}
                      placeholder={t('deploymentInputParam.placeholder')}
                      readOnly={editStatus}
                      className={cx('param-input')}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div
              className={cx(
                'variables-box',
                'close',
                readOnly ? 'readOnly' : 'editable',
              )}
            >
              <div className={cx('variables-title')}>
                {t('deploymentParams.label')}
              </div>
              <div className={cx('input-box')}>
                <div className={cx('input')}>
                  {variablesValues.map((v, i) => {
                    return (
                      <div className={cx('input-col')} key={i}>
                        <div className={cx('first-input')}>
                          <input
                            type='text'
                            value={v.name}
                            onChange={(e) =>
                              variableInputHandler({ e, idx: i, key: 'key' })
                            }
                            placeholder={t('deploymentInputKey.placeholder')}
                            readOnly={editStatus}
                            className={cx('key-input')}
                          />
                        </div>
                        <div className={cx('second-input')}>
                          <input
                            type='text'
                            value={v.value}
                            onChange={(e) =>
                              variableInputHandler({ e, idx: i, key: 'value' })
                            }
                            placeholder={t('deploymentInputValue.placeholder')}
                            readOnly={editStatus}
                            className={cx('value-input')}
                          />
                        </div>
                        <div
                          className={cx('image')}
                          onClick={() => {
                            if (!editStatus) variablesDelete(i);
                          }}
                        >
                          <img
                            className={cx('img', editStatus && 'img-disable')}
                            src={deleteImage}
                            alt='type'
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className={cx('btn')}>
                  <button
                    className={cx('variable-btn')}
                    onClick={() => {
                      if (!editStatus) variablesAdd();
                    }}
                  >
                    <img
                      className={cx('plus')}
                      src={plusImage}
                      alt='add'
                      width={14}
                      height={14}
                    />
                    {t('deploymentAddParams.label')}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
    </div>
  );
}

export default TrainingType;
