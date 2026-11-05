import { getPlaygroundRagList } from '@src/apis/llm/playground';
import IconRag from '@src/static/images/icon/rag-icon.svg';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import PlaygroundDropdown from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundDropdown';

import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import { closeModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './ImportRagModal.module.scss';

const cx = classNames.bind(style);

const calRagList = (toggleValue, ragList, userName) => {
  if (toggleValue.value === 0) return ragList;
  const copyList = ragList.slice();
  const ownerList = copyList.filter((el) => el.owner === userName);
  return ownerList;
};

const getPlaygroundRagInfo = async (workspaceId, setRagList) => {
  const { result, message, status, error } = await getPlaygroundRagList(
    workspaceId,
  );
  if (status === STATUS_SUCCESS) {
    const transformResult = result.map((el) => {
      return {
        ...el,
        backname: el.owner,
      };
    });
    setRagList(transformResult);
  } else {
    errorToastMessage(error, message);
  }
};

const ImportRagModal = ({ data, type }) => {
  const { t } = useTranslation();
  const { workspaceId, playgroundId } = data;

  const { rag } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const dispatch = useDispatch();

  const title = useMemo(() => {
    return `RAG ${t('getInfo.label')}`;
  }, [t]);

  const toggleList = [
    {
      label: t('total.label'),
      value: 0,
    },
    { label: t('me.label'), value: 1 },
  ];
  const [toggleValue, setToggleValue] = useState(toggleList[0]);

  const [ragList, setRagList] = useState([]);
  const [selectedValue, setSelectedValue] = useState({
    id: null,
  });

  const options = calRagList(toggleValue, ragList, userName);

  useEffect(() => {
    getPlaygroundRagInfo(workspaceId, setRagList);
  }, [workspaceId]);

  return (
    <NewStyleModalFrame
      submit={{
        text: t('select.label'),
        func: async () => {
          dispatch(
            handleSetPlaygroundState({
              type: 'rag',
              rag: {
                ...rag,
                is_rag: true,
                rag_id: selectedValue.id,
                rag_name: selectedValue.name,
                chunk_len: selectedValue.chunk_len,
                chunk_max: 10,
                docs_total_count: selectedValue.docs_total_count,
                docs_total_size: selectedValue.docs_total_size,
                rag_doc_list: selectedValue.doc_list,
                embedding_huggingface_model_id:
                  selectedValue.embedding_huggingface_model_id,
                reranker_huggingface_model_id:
                  selectedValue.reranker_huggingface_model_id,
              },
            }),
          );
          dispatch(closeModal(type));
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      type={type}
      validate={selectedValue.id}
      isResize={true}
      isMinimize={true}
      title={title}
      // footerMessage={validateMessage(t, instance_list, last_free_resource)}
      customStyle={{ width: '664px' }}
    >
      <PlaygroundDropdown
        label={t('template.model.label')}
        icon={IconRag}
        options={options}
        placeholder={t('playground.import.rag.message')}
        value={selectedValue}
        handleSelected={setSelectedValue}
        visibilityLabel={t('creator.label')}
        visiblityList={toggleList}
        visibilityValue={toggleValue}
        handleVisibility={setToggleValue}
      />
    </NewStyleModalFrame>
  );
};

export default ImportRagModal;
