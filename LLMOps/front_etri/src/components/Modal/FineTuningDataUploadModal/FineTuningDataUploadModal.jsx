import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText, Radio, Textarea } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';
import DatasetUploadSearchCom from './DatasetUploadSearchCom';
import FinetuningDatasetSearch from './FinetuningDatasetSearch';
import SearchComponent from './SearchComponent';

import { copyToClipboard, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './FineTuningDataUploadModal.module.scss';

import copyIcon from '@src/static/images/icon/00-ic-basic-copy-o.svg';
import IconTraining from '@src/static/images/icon/ic-data-training-llm.png';

const cx = classNames.bind(style);

const noSelectedDataMessage = {
  first: 'datasetSelect.message',
  second: 'trainingDataSelect.message',
};

const title = {
  first: 'dataset.label',
  second: 'trainingData.label',
};

const initialModelData = {
  keyword: '',
  selectedModel: null,
  selectedOption: {
    label: 'total.label',
    value: 'total',
  },
};

// ** [계산]
const calIsFooterMessage = (selectedDataset, selectedData) => {
  if (!selectedDataset.id || selectedDataset.id === '') {
    return 'finetuning.datasetNotice.message';
  }
  if (!selectedData.name || selectedData.name === '') {
    return 'trainingDataSelect.message';
  }

  // if (!selectedData.type || selectedData.type !== 'file') {
  //   return 'trainingDataSelect.message';
  // }

  return null;
};

const FineTuningDataUploadModal = ({ data, type }) => {
  const { workspaceId, refresh, modelId, git } = data;

  const dispatch = useDispatch();

  const [loadType, setLoadType] = useState(1); // 1 , 0
  const [footerMessage, setFooterMessage] = useState('');

  const [datasetList, setDatasetList] = useState([]);
  const [trainingList, setTrainingList] = useState([]);

  const [validate, setValidate] = useState(false);

  const [modelData, setModelData] = useState({
    modelName: '',
    modelDesc: '',
  });

  const [datasetData, setDatasetData] = useState(initialModelData);
  const [trainingData, setTrainingData] = useState(initialModelData);

  const [selectDataset, setSelectedDataset] = useState({ id: '', name: '' });
  const [selectData, setSelectedData] = useState({ name: '', fullPath: '' });

  const onChange = (label, value) => {
    if (label === 'name') {
      setModelData({
        ...modelData,
        modelName: value,
      });
    } else {
      setModelData({
        ...modelData,
        modelDesc: value,
      });
    }
  };

  // list 클릭
  const onClickList = (model, type) => {
    if (type === 'first') {
      setDatasetData((prev) => ({
        ...prev,
        // or ...initialModelData,
        selectedModel: model,
      }));
      setTrainingData(initialModelData);
    } else {
      setTrainingData((prev) => ({
        ...prev,
        selectedModel: model,
      }));
    }
  };

  const { t } = useTranslation();

  // sub menu 클릭
  const onClickSubMenu = async (selectedItem, type) => {
    if (type === 'first') {
      setDatasetData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    } else {
      setTrainingData((prev) => ({
        ...prev,
        selectedOption: selectedItem,
      }));
    }
  };

  // POST Submit TrainingPage
  const postDatasetFiles = async () => {
    // const { id } = datasetData.selectedModel; // dataset id
    // const { name } = trainingData.selectedModel; // path

    const response = await callApi({
      url: `models/option/add-dataset`,
      method: 'post',
      body: {
        dataset_id: selectDataset.id,
        training_data_path: selectData.fullPath,
        model_id: modelId,
      },
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('FINETUNING_DATA_UPLOAD'));
      refresh();
    } else {
      errorToastMessage(error, message);
    }
  };

  // 링크 복사
  const copyLink = () => {
    copyToClipboard(git ?? '');
    toast.success(t('copyToClipboard.success.message'));
  };

  // GET 데이터셋
  const getDataset = useCallback(
    async ({ keyword = '' } = {}) => {
      setDatasetData((prev) => ({
        ...prev,
        keyword,
      }));

      const isMine = datasetData.selectedOption.value === 'me';

      let url = `models/option/datasets?workspace_id=${workspaceId}&dataset_name=${keyword}&is_mine=${isMine}`;

      const response = await callApi({
        url,
        method: 'get',
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setDatasetList(result);
      } else {
        errorToastMessage(error, message);
      }
    },
    [datasetData.selectedOption.value, workspaceId],
  );

  // GET 학습
  const getTraining = async ({ keyword = '', id } = {}) => {
    setTrainingData((prev) => ({
      ...prev,
      keyword,
    }));
    let url = `models/option/dataset-files?dataset_id=${
      id ? id : datasetData.selectedModel.id
    }&search=${keyword}`;

    const response = await callApi({
      url,
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const transFormedData = result.map(({ file_path, ...rest }) => ({
        name: file_path,
        ...rest,
      }));
      setTrainingList(transFormedData);
    } else {
      errorToastMessage(error, message);
    }
  };

  const modelValidate = useCallback(() => {
    let validation = 0;
    let footerMessage = '';
    // finetuning.datasetNotice.message
    // if (modelData.modelName === '') {
    //   validation++;
    //   footerMessage = 'modelName.message';
    // } else if (forbiddenChars.test(modelData.modelName)) {
    //   validation++;
    //   footerMessage = 'newNameRule.message';
    // } else

    if (!datasetData.selectedModel || !trainingData.selectedModel) {
      validation++;
      footerMessage = 'trainingDataSelect.message';
    }

    setFooterMessage(footerMessage);
    setValidate(validation === 0);
  }, [datasetData.selectedModel, trainingData.selectedModel]);

  const isFooterMessage = calIsFooterMessage(selectDataset, selectData);

  useEffect(() => {
    modelValidate();
  }, [modelData, loadType, modelValidate]);

  useEffect(() => {
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
    getDataset();
  }, [getDataset]);

  return (
    <NewStyleModalFrame
      title={t('trainingDataSelect.label')}
      type={type}
      submit={{
        text: t('select.label'),
        func: () => {
          postDatasetFiles();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={!isFooterMessage}
      isResize={true}
      isMinimize={true}
      customStyle={{ width: '664px' }}
      footerMessage={t(isFooterMessage)}
    >
      <div className={cx('row')}>
        {/* <DatasetUploadSearchCom
          firstData={datasetData}
          firstList={datasetList}
          secondData={trainingData}
          secondList={trainingList}
          firstIcon={IconTraining}
          firstSelectedItem={datasetData.selectedModel}
          secondSelectedItem={trainingData.selectedModel}
          onClick={onClickList}
          onSearchFirst={getDataset}
          tabMenuTitle={'creator.label'}
          onSearchSecond={getTraining}
          onClickSubMenu={onClickSubMenu}
          noSelectedDataMessage={noSelectedDataMessage}
          title={title}
          t={t}
        /> */}
        <FinetuningDatasetSearch
          workspaceId={workspaceId}
          selectData={selectData}
          setSelectedData={setSelectedData}
          selectDataset={selectDataset}
          setSelectedDataset={setSelectedDataset}
        />
        <div className={cx('dataset-notice')}>
          {t('finetuning.dataset.desc')}
        </div>
      </div>
      <div className={cx('link-box')}>
        <div className={cx('title')}>{t('datasetModelLink.label')}</div>
        <div className={cx('link')}>
          <div>{git ?? '-'}</div>
          <img
            src={copyIcon}
            alt='copy icon'
            onClick={copyLink}
            style={{ cursor: 'pointer' }}
          />
        </div>
        <div></div>
      </div>
    </NewStyleModalFrame>
  );
};

export default FineTuningDataUploadModal;
