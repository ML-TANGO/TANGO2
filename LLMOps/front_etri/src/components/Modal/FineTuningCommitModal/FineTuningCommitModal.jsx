import { InputText, Radio, Textarea } from '@tango/ui-react';

import { loadModalComponent } from '@src/modal';
import copyIcon from '@src/static/images/icon/00-ic-basic-copy-o.svg';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { copyToClipboard, errorToastMessage } from '@src/utils';

import SearchComponent from '../FineTuningDataUploadModal/SearchComponent';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './FineTuningCommitModal.module.scss';

const cx = classNames.bind(style);

const noSelectedDataMessage = {
  first: 'commitVersion.message',
};

const title = {
  first: 'commit.label',
};

const initialModelData = {
  keyword: '',
  selectedModel: null,
  selectedOption: {
    label: 'total.label',
    value: 'total',
  },
};

const FineTuningCommitModal = ({ data, type }) => {
  const { workspaceId, refresh, modelId, getCommitId } = data;

  const dispatch = useDispatch();

  const [loadType, setLoadType] = useState(1); // 1 , 0
  const [footerMessage, setFooterMessage] = useState('');

  const [commitList, setCommitList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [validate, setValidate] = useState(false);

  const [modelData, setModelData] = useState({
    modelName: '',
    modelDesc: '',
  });

  const [commitData, setCommitData] = useState(initialModelData);
  const [trainingData, setTrainingData] = useState(initialModelData);

  // list 클릭
  const onClickList = (model, type) => {
    setCommitData((prev) => ({
      ...prev,
      // or ...initialModelData,
      selectedModel: model,
    }));
  };

  const { t } = useTranslation();

  // sub menu 클릭
  const onClickSubMenu = async (selectedItem) => {
    setCommitData((prev) => ({
      ...prev,
      selectedOption: selectedItem,
    }));
  };

  // get Submit TrainingPage
  const onSubmit = async () => {
    setLoading(true);
    const { id } = commitData.selectedModel; // commit id

    const response = await callApi({
      url: `models/commit-models/load`,
      method: 'POST',
      body: id,
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      getCommitId(id);
      dispatch(closeModal('FINETUNING_COMMIT_LOAD'));
      refresh();
    } else {
      errorToastMessage(message);
    }
    setLoading(false);
  };

  // GET Commit
  const getCommit = useCallback(
    async ({ keyword = '' } = {}) => {
      setCommitData((prev) => ({
        ...prev,
        keyword,
      }));

      const isMine = commitData.selectedOption.value === 'me';

      let url = `models/option/commit-models?model_id=${modelId}&search=${keyword}`;

      const response = await callApi({
        url,
        method: 'get',
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setCommitList(result);
      } else {
        errorToastMessage(error, message);
      }
    },
    [commitData.selectedOption.value, modelId],
  );

  const modelValidate = useCallback(() => {
    let validation = 0;
    let footerMessage = '';

    if (!commitData.selectedModel) {
      validation++;
      footerMessage = 'prompt.warning.label2';
    }

    setFooterMessage(footerMessage);
    setValidate(validation === 0);
  }, [commitData.selectedModel]);

  useEffect(() => {
    modelValidate();
  }, [modelData, loadType, modelValidate]);

  useEffect(() => {
    getCommit();
  }, [getCommit]);

  return (
    <NewStyleModalFrame
      title={t('commitLoad.label')}
      type={type}
      submit={{
        text: t('getInfo.label'),
        func: () => {
          onSubmit();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={validate}
      isResize={true}
      isLoading={loading}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <SearchComponent
          firstData={commitData}
          firstList={commitList}
          firstSelectedItem={commitData.selectedModel}
          onClick={onClickList}
          onSearchFirst={getCommit}
          onClickSubMenu={onClickSubMenu}
          noSelectedDataMessage={noSelectedDataMessage}
          title={title}
          t={t}
        />
      </div>
    </NewStyleModalFrame>
  );
};

export default FineTuningCommitModal;
