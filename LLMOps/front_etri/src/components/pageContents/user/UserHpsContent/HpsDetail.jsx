import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { Button, ButtonV2, InputText } from '@tango/ui-react';

import GrayDropDown from '@src/components/Modal/BasicFeeOptionModal/GrayDropDown';
import UsecaseList from '@src/components/organisms/UsecaseList';

import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import HpsBuiltInList from './HpsBuiltInList';
import HpsInfoList from './HpsInfoList';
import GrayArrowClose from '/images/icon/gray-close-arrow.svg';
import GrayArrowOpen from '/images/icon/gray-open-arrow.svg';

import classNames from 'classnames/bind';
import style from './HpsDetail.module.scss';

const cx = classNames.bind(style);

const HpsDetail = ({ wid, tid, setTrainName }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [hpsList, setHpsList] = useState([]);
  const [isAllOpen, setIsAllOpen] = useState(false); // 모두 펼치기/접기 상태
  const [isFirstRenderEnd, setIsFirstRenderEnd] = useState(false);
  const [hpsResource, setHpsResource] = useState({
    cpu: 0,
    ram: 0,
    gpu: 0,
    instanceName: '',
    instanceType: '',
  });
  const [keyword, setKeyword] = useState('');
  const [searchType, setSearchType] = useState({
    label: 'HPS 이름',
    value: 'name',
  });
  const [trainType, setTrainType] = useState('advanced');
  const [searchList, setSearchList] = useState([
    { label: 'HPS 이름', value: 'name' },
    { label: '도커 이미지', value: 'image' },
    { label: '실행 코드', value: 'runCode' },
    // { label: '생성자', value: 'runnerName' },
  ]);

  const handleToggleAll = (open) => {
    setIsAllOpen(open);
  };

  const handleSearchType = ({ value, label }) => {
    setSearchType({ label, value });
  };

  const openHpsCreateModal = () => {
    dispatch(
      openModal({
        modalType:
          trainType === 'advanced'
            ? 'HPS_CUSTOM_CREATE'
            : 'HPS_BUILT_IN_CREATE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {},
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceId: wid,
          trainId: tid,
        },
      }),
    );
  };

  const usecaseList = [
    {
      title: t('hps.usecase1.title.message'),
      description: t('hps.usecase1.desc.message'),
      button: (
        <Button
          type='primary'
          onClick={openHpsCreateModal}
          customStyle={{ borderRadius: '7px' }}
        >
          {t('createHPS.label')}
        </Button>
      ),
    },
    {
      title: t('hps.usecase2.title.message'),
      description: t('hps.usecase2.desc.message'),
      button: (
        <Button
          type='primary'
          onClick={openHpsCreateModal}
          customStyle={{ borderRadius: '7px' }}
        >
          {t('createHPS.label')}
        </Button>
      ),
    },
    {
      title: t('hps.usecase3.title.message'),
      description: t('hps.usecase3.desc.message'),
      button: (
        <Button
          type='primary'
          onClick={openHpsCreateModal}
          customStyle={{ borderRadius: '7px' }}
        >
          {t('createHPS.label')}
        </Button>
      ),
    },
  ];

  const fetchHpsList = async () => {
    const response = await callApi({
      url: `projects/hps?project_id=${tid}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS && result) {
      const { list, project_info, hps_resource } = result;
      const hpsList = list.map(
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
          built_in_search_count,
          log_file,
          gpu_count,
          end_datetime,
        }) => ({
          id,
          name,
          createAt: create_datetime,
          startAt: start_datetime,
          endAt: end_datetime,
          image: image_name,
          runCode: run_code ?? '',
          parameter: parameter,
          instance: project_info.instance_name,
          gpu: gpu_count,
          status: status.status,
          dataset: dataset_name,
          dataPath: dataset_data_path,
          searchCount: built_in_search_count,
          isResult: log_file,
        }),
      );

      setHpsList(hpsList);
      setHpsResource({
        ram: hps_resource.ram,
        cpu: hps_resource.cpu,
        gpu: hps_resource.gpu,
        instanceName: hps_resource.resource_name,
        instanceType: project_info.instance_type,
      });
      setTrainType(project_info.type);
      setTrainName(project_info.name);
    }

    setIsFirstRenderEnd(true);
  };

  const deleteAllHps = async () => {
    const response = await callApi({
      url: 'projects/hps',
      method: 'delete',
      body: {
        project_id: tid,
      },
    });
  };

  const deleteHpsConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteAllHPSPopup.title.label',
        content: 'deleteAllHpsPopup.message',
        testid: 'hps-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            deleteAllHps();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: '전체 삭제',
      }),
    );
  };

  // * 학습 결과 모달
  const handleResultModal = (id) => {
    dispatch(
      openModal({
        modalType: 'HPS_RESULT_MODAL',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              // getAnalysisList(setAnalysisList, wid);
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          trainingId: id,
          modalType: 'ADD_DATASET_ANALYSIS',
        },
      }),
    );
  };

  useEffect(() => {
    loadModalComponent('HPS_RESULT_MODAL');
  }, []);

  useEffect(() => {
    fetchHpsList();

    const intervalFetchDevTool = setInterval(() => {
      fetchHpsList();
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
            <img src='/images/icon/ic-hps.svg' alt='icon' />
          </div>
          <span>HPS</span>
        </div>
        <div className={cx('right-side')}>
          <div className={cx('instance-info')}>
            <div className={cx('type')}>
              <span>HPS별 가용 vGPU 구성</span>
              <span>HPS별 vCPU 제공량</span>
              <span>HPS별 RAM 제공량</span>
            </div>
            <div className={cx('value')}>
              <span>
                {hpsResource.gpu
                  ? `${hpsResource.instanceName} x ${hpsResource.gpu}EA`
                  : '-'}
              </span>
              <span>{hpsResource.cpu} Cores</span>
              <span>{hpsResource.ram} GB</span>
            </div>
          </div>
          <ButtonV2
            colorType='blue'
            label={t('createHPS.label')}
            onClick={openHpsCreateModal}
            size='l'
          />
        </div>
      </div>
      {(hpsList.length === 0 || !hpsList) && (
        <div className={cx('empty-box')}>
          <div className={cx('left-box')}>
            <div className={cx('title')}>Hyperparameter Search</div>
            <div className={cx('description')}>
              {t('hps.emptycase.desc.message')}
            </div>
            <div className={cx('img')}>
              <img src='/images/icon/hps-empty.png' alt='' />
            </div>
          </div>
          <div className={cx('right-box')}>
            <UsecaseList list={usecaseList} />
          </div>
        </div>
      )}
      {hpsList.length > 0 && (
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
              label={'전체 삭제'}
              onClick={deleteHpsConfirmPopup}
              size='l'
              colorType='lightRed'
            />
          </div>
        </div>
      )}

      {hpsList
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
            searchCount,
            isResult,
            endAt,
          }) =>
            trainType === 'advanced' ? (
              <HpsInfoList
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
                isResult={isResult}
                endAt={endAt}
                handleResultModal={handleResultModal}
              />
            ) : (
              <HpsBuiltInList
                key={id}
                id={id}
                name={name}
                createAt={createAt}
                image={image}
                dataset={dataset}
                startAt={startAt}
                gpu={gpu}
                parameter={parameter}
                status={status}
                isAllOpen={isAllOpen}
                dataPath={dataPath}
                searchCount={searchCount}
                isResult={isResult}
                endAt={endAt}
                handleResultModal={handleResultModal}
              />
            ),
        )}
    </div>
  );
};

export default HpsDetail;
