import { ButtonV2 } from '@jonathan/ui-react';

import {
  getPlaygroundTestDataset,
  getPlaygroundTestOptions,
  postPlaygroundTestChat,
} from '@src/apis/llm/playground';
import IconDatasetBlack from '@src/static/images/icon/dataset-black.svg';
import ErrorIcon from '@src/static/images/icon/error-o.svg';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import DoubleDropdown from '@src/components/Modal/ImportPromptModal/DoubleDropdown';

import { STATUS_SUCCESS } from '@src/network';

import DatasetComTable from './DatasetComTable';

// CSS Module
import classNames from 'classnames/bind';
import style from './DatasetCom.module.scss';

const cx = classNames.bind(style);

const initialOptions = {
  datasetOptions: [],
  trainDatasetOptions: [],
};

const datasetInitial = {
  datasetValue: { id: null, name: null },
  trainDatasetValue: { id: null, name: null, input_list: [] },
};
const visiblityList = [
  { label: '전체', value: 0 },
  { label: '본인', value: 1 },
];

const initialVisibilty = {
  datasetVisibility: visiblityList[0],
  trainDatasetVisibility: visiblityList[0],
};

const calFilterDataList = (list, visibility, userName) => {
  const { value } = visibility;
  if (value === 1) {
    const filterList = list.filter((el) => el.owner === userName);
    return filterList;
  }
  return list;
};

const getPlaygroundDatasetOptions = async (playgroundId, setOptions) => {
  const { status, message, result } = await getPlaygroundTestOptions(
    playgroundId,
  );
  if (status === STATUS_SUCCESS) {
    const transformList = result.dataset_list.map((el) => ({
      ...el,
      owner: el.create_user_name,
    }));
    setOptions((prev) => ({
      ...prev,
      datasetOptions: transformList,
      testUrl: result.test_url,
    }));
  } else {
    toast.error(message);
  }
};

const getTrainDatasetOptions = async (datasetValue, setOptions) => {
  const { result, status, message } = await getPlaygroundTestDataset(
    datasetValue.id,
  );
  if (status === STATUS_SUCCESS) {
    const transformList = result.map((el) => {
      const inputList = el.input_list.map((input) => {
        return {
          input,
          output: '',
          time: '',
        };
      });
      return {
        ...el,
        type: 'input',
        input_list: inputList,
        name: el.file_name,
      };
    });
    setOptions((prev) => ({
      ...prev,
      trainDatasetOptions: transformList,
    }));
  } else {
    toast.error(message);
  }
};

export default function DatasetCom({ playgroundId }) {
  const { t } = useTranslation();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const session_id = sessionStorage.getItem('loginedSession');

  const [options, setOptions] = useState(initialOptions);
  const { datasetOptions, trainDatasetOptions } = options;

  const [isOpen, setIsOpen] = useState({
    firstIsOpen: true,
    secondIsOpen: false,
  });
  const { firstIsOpen, secondIsOpen } = isOpen;

  const [visibility, setVisibility] = useState(initialVisibilty);
  const { datasetVisibility, trainDatasetVisibility } = visibility;

  const [selectedValue, setSelectedValue] = useState(datasetInitial);
  const { datasetValue, trainDatasetValue } = selectedValue;
  const { id: datasetId } = datasetValue;
  const { input_list, file_name, type: trainType } = trainDatasetValue;

  const filterDataList = calFilterDataList(
    datasetOptions,
    datasetVisibility,
    userName,
  );

  const isTestBtn = datasetValue.id && trainDatasetValue.name;
  const [isLoadingTestBtn, setIsLoadingTestBtn] = useState(false);

  const handleVisibility = (value, type) => {
    setVisibility((prev) => ({
      ...prev,
      [type]: value,
    }));
  };

  const handleSelected = (value, type) => {
    setSelectedValue((prev) => ({
      ...prev,
      [type]: value,
    }));
    if (type === 'datasetValue') {
      setIsOpen((prev) => ({
        firstIsOpen: !prev.firstIsOpen,
        secondIsOpen: !prev.secondIsOpen,
      }));
    }

    if (type === 'trainDatasetValue') {
      setIsOpen((prev) => ({
        ...prev,
        secondIsOpen: false,
      }));
    }
  };

  const handleTest = async (
    playgroundId,
    datasetId,
    file_name,
    session_id,
    isLoadingTestBtn,
    setIsLoadingTestBtn,
  ) => {
    if (isLoadingTestBtn) return;
    setIsLoadingTestBtn(true);
    const { status, result, message } = await postPlaygroundTestChat({
      playground_id: playgroundId,
      test_type: 'dataset',
      test_dataset_id: datasetId,
      test_dataset_filename: file_name,
      session_id,
    });

    if (status === STATUS_SUCCESS) {
      const transformList = result.map((el) => {
        return {
          ...el,
          time: `${el.time.toFixed(2)} 초`,
        };
      });
      setSelectedValue((prev) => {
        return {
          ...prev,
          trainDatasetValue: {
            ...prev.trainDatasetValue,
            type: 'output',
            input_list: transformList,
          },
        };
      });
    } else {
      toast.error(message);
    }
    setIsLoadingTestBtn(false);
  };

  useEffect(() => {
    getPlaygroundDatasetOptions(playgroundId, setOptions);
  }, [playgroundId]);

  useEffect(() => {
    if (!datasetValue.id) return;
    getTrainDatasetOptions(datasetValue, setOptions);
  }, [datasetValue]);

  return (
    <div>
      <DoubleDropdown
        key={'dataset'}
        label={t('dataset')}
        placeholder={t('dataset.placeholder')}
        visibilityLabel={t('owner.label')}
        isOpen={firstIsOpen}
        options={filterDataList}
        icon={IconDatasetBlack}
        visiblityList={visiblityList}
        visibilityValue={datasetVisibility}
        handleIsOpen={(value) => {
          if (isLoadingTestBtn) return;
          setIsOpen((prev) => ({
            ...prev,
            firstIsOpen: value,
            secondIsOpen: !value,
          }));
          setSelectedValue(datasetInitial);
          setOptions((prev) => ({
            ...prev,
            trainDatasetOptions: [],
          }));
        }}
        handleSelected={(value) => handleSelected(value, 'datasetValue')}
        handleVisibility={(value) =>
          handleVisibility(value, 'datasetVisibility')
        }
        value={datasetValue}
        outerStyle={{
          borderRadius: '10px 10px 0 0',
          borderBottom: !firstIsOpen && 'none',
        }}
        innerStyle={{ borderRadius: '0px', borderBottom: 'none' }}
      />
      <DoubleDropdown
        key={'trainingData'}
        label={t('trainingData.label')}
        placeholder={t('dataset.placeholder')}
        visibilityLabel={t('owner.label')}
        icon={IconDatasetBlack}
        isOpen={secondIsOpen}
        options={trainDatasetOptions}
        value={trainDatasetValue}
        visiblityList={visiblityList}
        visibilityValue={trainDatasetVisibility}
        handleIsOpen={(value) => {
          if (isLoadingTestBtn) return;
          setIsOpen((prev) => ({
            ...prev,
            firstIsOpen: false,
            secondIsOpen: value,
          }));
          setSelectedValue((prev) => ({
            ...prev,
            trainDatasetValue: datasetInitial.trainDatasetValue,
          }));
        }}
        handleVisibility={(value) =>
          handleVisibility(value, 'trainDatasetVisibility')
        }
        handleSelected={(value) => handleSelected(value, 'trainDatasetValue')}
        outerStyle={{
          borderRadius: `${secondIsOpen ? '0px' : '0 0 10px 10px'}`,
        }}
        innerStyle={{ borderRadius: '0 0 10px 10px' }}
      />
      <div className={cx('message-cont')}>
        <img src={ErrorIcon} alt='error-icon' />
        <p className={cx('warn-message')}>데이터셋을 문장 단위로 넣어주세요.</p>
      </div>
      <div className={cx('btn-cont')}>
        <ButtonV2
          label={t('test.label')}
          colorType='skyblue'
          disabled={!isTestBtn}
          isLoading={isLoadingTestBtn}
          onClick={() =>
            handleTest(
              playgroundId,
              datasetId,
              file_name,
              session_id,
              isLoadingTestBtn,
              setIsLoadingTestBtn,
            )
          }
        />
      </div>
      <DatasetComTable type={trainType} list={input_list} />
    </div>
  );
}
