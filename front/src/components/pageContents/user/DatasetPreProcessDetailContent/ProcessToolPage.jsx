import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { Button, ButtonV2, InputText } from '@jonathan/ui-react';

import GrayDropDown from '@src/components/Modal/BasicFeeOptionModal/GrayDropDown';
import UsecaseList from '@src/components/organisms/UsecaseList';

import { openConfirm } from '@src/store/modules/confirm';
import { callApi, STATUS_SUCCESS } from '@src/network';

import ProcessJobBuiltInDetail from './ProcessJobBuiltInDetail';
import ProcessJobDetail from './ProcessJobDetail';
import GrayArrowClose from '/images/icon/gray-close-arrow.svg';
import GrayArrowOpen from '/images/icon/gray-open-arrow.svg';

import classNames from 'classnames/bind';
import style from './ProcessToolPage.module.scss';

const cx = classNames.bind(style);

const ProcessToolPage = ({
  openJobCreateModal,
  did,
  wid,
  processType,
  setBuiltInDataType,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [jobList, setJobList] = useState([]);
  const [isAllOpen, setIsAllOpen] = useState(false); // 모두 펼치기/접기 상태
  const [isFirstRenderEnd, setIsFirstRenderEnd] = useState(false);
  const [jobResource, setJobResource] = useState({
    cpu: 0,
    ram: 0,
    gpu: 0,
    instanceName: '',
    instanceType: '',
  });
  const [keyword, setKeyword] = useState('');
  const [searchType, setSearchType] = useState({
    label: 'JOB 이름',
    value: 'name',
  });
  const [searchList, setSearchList] = useState([
    { label: 'JOB 이름', value: 'name' },
    { label: '도커 이미지', value: 'image' },
    { label: '생성자', value: 'runnerName' },
    { label: '실행 코드', value: 'runCode' },
  ]);

  const handleToggleAll = (open) => {
    setIsAllOpen(open);
  };

  const handleSearchType = ({ value, label }) => {
    setSearchType({ label, value });
  };

  const usecaseList = [
    {
      title: t('job.usecase1.title.message'),
      description: t('job.usecase1.desc.message'),
      button: (
        <Button type='primary' onClick={openJobCreateModal}>
          {t('createJob.label')}
        </Button>
      ),
    },
    {
      title: t('job.usecase2.title.message'),
      description: t('job.usecase2.desc.message'),
      button: (
        <Button type='primary' onClick={openJobCreateModal}>
          {t('createJob.label')}
        </Button>
      ),
    },
    {
      title: t('job.usecase3.title.message'),
      description: t('job.usecase3.desc.message'),
      button: (
        <Button type='primary' onClick={openJobCreateModal}>
          {t('createJob.label')}
        </Button>
      ),
    },
  ];

  const fetchJobList = async () => {
    const response = await callApi({
      url: `preprocessing/jobs?preprocessing_id=${did}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS && result) {
      const { list, preprocessing_info } = result;
      const { instance_info } = preprocessing_info;

      const jobList = list.map(
        ({
          id,
          name,
          create_datetime,
          start_datetime,
          image_name,
          run_code,
          parameter,
          status,
          dataset_name,
          dataset_data_path,
          log_file,
          runner_name,
          end_datetime,
          gpu_count,
        }) => ({
          id,
          name,
          createAt: create_datetime,
          startAt: start_datetime,
          endAt: end_datetime,
          image: image_name,
          runCode: run_code ?? '',
          parameter: parameter,
          instance: instance_info.instance_name,
          gpu: gpu_count,
          status: status.status,
          dataset: dataset_name,
          dataPath: dataset_data_path,
          canLogDownload: log_file,
          runnerName: runner_name ?? '',
        }),
      );
      setJobList(jobList);
      setJobResource({
        ram: instance_info.ram_allocate,
        cpu: instance_info.cpu_allocate,
        gpu: instance_info.gpu_allocate,
        instanceName: instance_info.instance_name,
        instanceType: instance_info.instance_type,
      });
      setBuiltInDataType(preprocessing_info.built_in_data_type);
    }

    setIsFirstRenderEnd(true);
  };

  const deleteAllTool = async () => {
    const response = await callApi({
      url: 'preprocessing/jobs/all',
      method: 'delete',
      body: {
        preprocessing_id: did,
      },
    });
  };

  const deleteToolConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteAllJobPopup.title.label',
        content: 'deleteAllJobPopup.message',
        testid: 'job-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            deleteAllTool();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: '전체 삭제',
      }),
    );
  };

  useEffect(() => {
    fetchJobList();

    const intervalFetchDevTool = setInterval(() => {
      fetchJobList();
    }, 1000);

    return () => {
      clearInterval(intervalFetchDevTool);
    };
  }, []);

  if (!isFirstRenderEnd) {
    return <></>;
  }

  return (
    <div className={cx('container')}>
      <div className={cx('header-content')}>
        <div className={cx('left-side')}>
          <div className={cx('icon-box')}>
            <img src='/images/icon/ic-job.svg' alt='icon' />
          </div>
          <span>JOB</span>
        </div>
        <div className={cx('right-side')}>
          <div className={cx('type')}>
            <span>JOB 별 가용 vGPU 구성</span>
            <span>JOB 별 vCPU 제공량</span>
            <span>JOB 별 RAM 제공량</span>
          </div>
          <div className={cx('value')}>
            <span>
              {jobResource.instanceType === 'GPU'
                ? `${jobResource.instanceName} x ${jobResource.gpu}EA`
                : '-'}
            </span>
            <span>{jobResource.cpu ? `${jobResource.cpu} Cores` : '-'}</span>
            <span>{jobResource.ram ? `${jobResource.ram} GB` : '-'}</span>
          </div>
        </div>
      </div>
      {(jobList.length === 0 || !jobList) && (
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
            {/* <UsecaseList list={usecaseList} /> */}
          </div>
        </div>
      )}
      {jobList.length > 0 && (
        <div className={cx('option-container')}>
          <div className={cx('left-option')}>
            <div
              className={cx('all-btn')}
              onClick={() => handleToggleAll(true)}
            >
              <span>모두 펼치기</span>
              <img width={16} height={16} src={GrayArrowClose} alt='open' />
            </div>
            <div
              className={cx('all-btn')}
              onClick={() => handleToggleAll(false)}
            >
              <span>모두 접기</span>
              <img width={16} height={16} src={GrayArrowOpen} alt='close' />
            </div>
            <div className={cx('all-btn')}></div>
          </div>
          <div className={cx('right-option')}>
            <GrayDropDown
              list={searchList}
              value={searchType}
              customStyle={{ width: '220px' }}
              isCloseBorder={false}
              handleSelectOption={handleSearchType}
            />
            <InputText
              value={keyword}
              type='medium'
              placeholder={t('search.placeholder')}
              leftIcon='/images/icon/ic-search.svg'
              closeIcon='/images/icon/close-c.svg'
              onChange={(e) => setKeyword(e.target.value)}
              onClear={() => setKeyword('')}
              customStyle={{ width: '220px' }}
              disableLeftIcon={false}
              disableClearBtn={false}
            />
            <ButtonV2
              type='solid'
              colorType='lightRed'
              size='l'
              label={'전체 삭제'}
              onClick={deleteToolConfirmPopup}
            />
          </div>
        </div>
      )}

      {jobList
        .filter((v) => v[searchType.value].includes(keyword))
        .map(
          ({
            id,
            name,
            createAt,
            image,
            dataset,
            runCode,
            startAt,
            gpu,
            instance,
            parameter,
            status,
            dataPath,
            canLogDownload,
            endAt,
          }) =>
            processType === 'advanced' ? (
              <ProcessJobDetail
                key={id}
                id={id}
                wid={wid}
                name={name}
                createAt={createAt}
                image={image}
                dataset={dataset}
                runCode={runCode}
                startAt={startAt}
                gpu={gpu}
                instance={instance}
                parameter={parameter}
                status={status}
                isAllOpen={isAllOpen}
                processType={processType}
                endAt={endAt}
              />
            ) : (
              <ProcessJobBuiltInDetail
                key={id}
                id={id}
                wid={wid}
                name={name}
                createAt={createAt}
                dataset={dataset}
                startAt={startAt}
                gpu={gpu}
                parameter={parameter}
                status={status}
                isAllOpen={isAllOpen}
                dataPath={dataPath}
                canLogDownload={canLogDownload}
                endAt={endAt}
              />
            ),
        )}
    </div>
  );
};

export default ProcessToolPage;
