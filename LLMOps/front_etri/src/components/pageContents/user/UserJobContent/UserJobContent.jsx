// Components
import { Fragment, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { Button, InputText, Selectbox } from '@tango/ui-react';

import Loading from '@src/components/atoms/loading/Loading';
import PageTitle from '@src/components/atoms/PageTitle';
import EmptyBox from '@src/components/molecules/EmptyBox';
import UsecaseList from '@src/components/organisms/UsecaseList';

import { openModal } from '@src/store/modules/modal';

import JobAdvancedList from './JobAdvancedList';
import JobBuiltInList from './JobBuiltInList';

import classNames from 'classnames/bind';
import style from './UserJobContent.module.scss';

import ArrowIcon from '@src/static/images/icon/ic-left.svg';

const cx = classNames.bind(style);

const UserJobContent = ({
  wid,
  tid,
  jobListData,
  totalJobRows,
  jobSearchKey,
  jobKeyword,
  onJobSearchKeyChange,
  onJobSearch,
  onCreateJob,
  openDeleteConfirmPopup,
  onSelect,
  deleteBtnDisabled,
  // createBtnDisabled,
  trainingInfo,
  onViewJobLog,
  selectedRows,
  // onStopJob,
  onStopJob,
  isLoadingStopBtn,
  loading,
  jobResource,
  openGuideModal,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const {
    type: trainingType,
    name: trainingName,
    image: dockerImageName,
    modelName: gpuModel,
    instance_allocate: gpuCount,
    instance_type: inStanceType, // gpu cpu
    gpu_allocate: gpuAllocate, // type cpu시 gpu allocate로 표시
    cpu_allocate: cpuAllocate,
    ram_allocate: ramAllocate,
  } = trainingInfo;
  const [isAllOpen, setIsAllOpen] = useState(false);

  const jobSearchOptions = [
    { label: t('jobName.label'), value: 'name' },
    { label: t('dockerImage.label'), value: 'image_name' },
    // { label: t('datasets.label'), value: 'dataset_name' },
    { label: t('creator.label'), value: 'runner_name' },
  ];

  if (trainingType === 'advanced') {
    jobSearchOptions.push({ label: t('runCode.label'), value: 'run_code' });
  }

  const manualOpenHandler = (boolean) => {
    setIsAllOpen(boolean);
  };

  const handleJobCreateHugging = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_JOB_HUGGING',
        modalData: {
          workspaceId: wid,
          tid,
          gpuCount,
          gpuModel,
        },
      }),
    );
  };

  const jobList =
    jobListData &&
    jobListData.map((list, index) =>
      trainingInfo.type === 'advanced' ? (
        <JobAdvancedList
          key={index}
          data={list}
          id={list.id}
          name={list.name}
          createAt={list.create_datetime}
          image={list.image_name}
          runCode={list.run_code}
          startAt={list.start_datetime}
          gpu={list.gpu_count}
          parameter={list.parameter}
          status={list.status.status}
          isAllOpen={isAllOpen}
          isResult={list.log_file}
          endAt={list.end_datetime}
          onViewLog={onViewJobLog}
          openDeleteConfirmPopup={openDeleteConfirmPopup}
          logFile={list.log_file}
          dataset={list.dataset_name ?? '-'}
          onStopJob={onStopJob}
          isLoadingStopBtn={isLoadingStopBtn}
          reason={list.status.reason}
        />
      ) : (
        <JobBuiltInList
          key={index}
          data={list}
          id={list.id}
          name={list.name}
          createAt={list.create_datetime}
          image={list.image_name}
          runCode={list.run_code}
          startAt={list.start_datetime}
          gpu={list.gpu_count}
          parameter={list.parameter}
          status={list.status.status}
          isAllOpen={isAllOpen}
          isResult={list.log_file}
          endAt={list.end_datetime}
          onViewLog={onViewJobLog}
          openDeleteConfirmPopup={openDeleteConfirmPopup}
          logFile={list.log_file}
          dataset={list.dataset_name ?? '-'}
          dataPath={list.dataset_data_path ?? '-'}
          onStopJob={onStopJob}
          isLoadingStopBtn={isLoadingStopBtn}
          reason={list.status.reason}
        />
      ),
    );

  const usecaseList = [
    {
      title: t('job.usecase1.title.message'),
      description: t('job.usecase1.desc.message'),
      button: (
        <Button
          type='primary-light'
          onClick={
            trainingInfo?.type === 'advanced'
              ? () => onCreateJob()
              : () => handleJobCreateHugging()
          }
        >
          {t('createJob.label')}
        </Button>
      ),
    },
    {
      title: t('job.usecase2.title.message'),
      description: t('job.usecase2.desc.message'),
      button: (
        <Button
          type='primary-light'
          onClick={onCreateJob}
          // disabled={createBtnDisabled}
        >
          {t('createJob.label')}
        </Button>
      ),
    },
    {
      title: t('job.usecase3.title.message'),
      description: t('job.usecase3.desc.message'),
      button: (
        <Button
          type='primary-light'
          onClick={onCreateJob}
          // disabled={createBtnDisabled}
        >
          {t('createJob.label')}
        </Button>
      ),
    },
  ];

  return (
    <div className={cx('content')}>
      <div className={cx('title-box')}>
        <PageTitle>{trainingName}</PageTitle>
        <button className={cx('visual-guide-btn')} onClick={openGuideModal}>
          {t('visualizationGuide.label')}
        </button>
      </div>
      <div className={cx('job-box')}>
        <div className={cx('name-box')}>
          <div className={cx('icon')}>
            <img src='/images/icon/ic-job.svg' alt='JOB icon' />
          </div>
          <label className={cx('label')}>JOB</label>
        </div>
        <div className={cx('info-box')}>
          <ul className={cx('info-list')}>
            <li>
              <label className={cx('label')}>{t('jobGpu.label')}</label>
              <span className={cx('value')}>
                {gpuModel || '-'} {gpuModel && `x ${jobResource.gpu}EA`}
              </span>
            </li>
            <li>
              <label className={cx('label')}>{t('jobCpu.label')}</label>
              <span className={cx('value')}>{jobResource?.cpu || 0} Cores</span>
            </li>
            <li>
              <label className={cx('label')}>{t('jobRam.label')}</label>
              <span className={cx('value')}>{jobResource.ram || 0} GB</span>
            </li>
          </ul>
          <div className={cx('btn-box')}>
            {trainingInfo?.type === 'advanced' ? (
              <button className={cx('create-job-btn')} onClick={onCreateJob}>
                + {t('createJob.label')}
              </button>
            ) : (
              <button
                className={cx('create-job-btn')}
                onClick={handleJobCreateHugging}
              >
                + {t('createJob.label')}
              </button>
            )}
          </div>
        </div>
      </div>
      <div className={cx('job-container')}>
        {jobList && totalJobRows > 0 && (
          <div className={cx('search-box')}>
            <div className={cx('filter-search')}>
              <div className={cx('search')}>
                <Fragment>
                  <div className={cx('job-menu-box')}>
                    <div className={cx('job-menu-left')}>
                      <Button
                        type='none-border'
                        onClick={() => manualOpenHandler(true)}
                        icon={ArrowIcon}
                        iconAlign='right'
                        iconStyle={{ transform: 'rotate(270deg)' }}
                        customStyle={{
                          padding: '8px',
                        }}
                      >
                        {t('allExpand.label')}
                      </Button>
                      <Button
                        type='none-border'
                        onClick={() => manualOpenHandler(false)}
                        icon={ArrowIcon}
                        iconAlign='right'
                        iconStyle={{ transform: 'rotate(90deg)' }}
                        customStyle={{
                          padding: '8px',
                          marginLeft: '4px',
                        }}
                      >
                        {t('allCollapse.label')}
                      </Button>
                    </div>
                    <div className={cx('job-menu-right')}>
                      <div>
                        <Selectbox
                          list={jobSearchOptions}
                          selectedItem={jobSearchKey}
                          onChange={onJobSearchKeyChange}
                          customStyle={{
                            fontStyle: {
                              selectbox: {
                                fontSize: '13px',
                              },
                            },
                          }}
                        />
                      </div>
                      <InputText
                        size='medium'
                        placeholder={t('search.placeholder')}
                        leftIcon='/images/icon/ic-search.svg'
                        value={jobKeyword}
                        onChange={(e) => {
                          onJobSearch(e.target.value);
                        }}
                        onClear={() => onJobSearch('')}
                        customStyle={{ width: '168px' }}
                        disableLeftIcon={false}
                      />
                    </div>
                  </div>
                </Fragment>
              </div>
            </div>
          </div>
        )}
        <div className={cx('contents-container')}>
          {loading ? (
            <div className={cx('loading-box')}>
              <Loading />
            </div>
          ) : totalJobRows === 0 ? (
            <div className={cx('empty-box')}>
              <div className={cx('left-box')}>
                <div className={cx('title')}>Queueing Experiments</div>
                <div className={cx('description')}>
                  {t('job.emptycase.desc.message')}
                </div>
                <div className={cx('img')}>
                  <img src='/images/icon/job-empty.png' alt='' />
                </div>
              </div>
              <div className={cx('right-box')}>
                <UsecaseList list={usecaseList} />
              </div>
            </div>
          ) : (
            <div className={cx('list-container')}>{jobList}</div>
          )}
          {!loading && totalJobRows !== 0 && jobList.length === 0 && (
            <div className={cx('no-result')}>
              <EmptyBox text={t('noSearchResult.message')} />
            </div>
          )}
        </div>
        {jobList && jobList.length > 0 && (
          <div className={cx('btn-box')}>
            <Button
              type='red-reverse'
              size='medium'
              onClick={() => openDeleteConfirmPopup(undefined, true)}
              customStyle={{ backgroundColor: 'transparent', border: 'none' }}
            >
              {t('deleteAll.label')}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UserJobContent;
