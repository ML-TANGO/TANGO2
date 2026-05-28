import { ButtonV2, Textarea } from '@jonathan/ui-react';

import { putRagDescription } from '@src/apis/llm/rag';
import { loadModalComponent } from '@src/modal';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { Prompt, useHistory, useRouteMatch } from 'react-router-dom';

import { toast } from '@src/components/Toast';

import { startPath } from '@src/store/modules/breadCrumb';
import { handleRagReset, handleSetRagState } from '@src/store/modules/llmRag';
import { openModal } from '@src/store/modules/modal';
// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import RagInstance from '../RagInstance';
import useSSESettingStatus from '../useSSESettingStatus';
import RagSettingCenter from './RagSettingCenter';
import RagSettingRight from './RagSettingRight';

import classNames from 'classnames/bind';
import style from './RagSetting.module.scss';

const cx = classNames.bind(style);

const RagSetting = memo(function RagSetting({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { id: workspaceId, rid: modelId } = match.params;
  const dispatch = useDispatch();
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const { setting, info, instance, settingStatus } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );

  const { rag, docs } = settingStatus || { rag: null, docs: null };

  // rag를 생성 중입니다.

  const [ragSetting, setRagSetting] = useState(null);
  const [backendData, setBackendData] = useState({});
  const [status, setStatus] = useState('running');
  const [reranker, setReranker] = useState(1);
  // const [settingStatus, setSettingStatus] = useState(null);
  const [embeddedList, setEmbeddedList] = useState([]);
  const [isDescription, setIsDescription] = useState(false);
  const [embeddedModel, setEmbeddedModel] = useState({
    keyword: '',
    selectedModel: '',
    selectedOption: {
      label: 'total.label',
      value: 'total',
    },
  });

  const { description } = info;
  const isLoading = useRef(false);
  const [chunkCount, setChunkCount] = useState(0);

  const openRagModelModal = (type) => {
    dispatch(
      openModal({
        modalType: 'RAG_EMBEDDING_MODAL',
        modalData: {
          workspaceId,
          refresh: () => console.log('get'),
          type,
        },
      }),
    );
  };

  // GET Embedded Model
  const getEmbedded = useCallback(
    async ({ keyword = '' } = {}) => {
      setEmbeddedModel((prev) => ({
        ...prev,
        keyword,
      }));

      const isMine = embeddedModel.selectedOption.value === 'me';

      let url = `models/option/commit-models?model_id=${modelId}&search=${keyword}`;

      const response = await callApi({
        url,
        method: ' ',
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setEmbeddedList(result);
      } else {
        errorToastMessage(error, message);
      }
    },
    [embeddedModel.selectedOption.value, modelId],
  );

  // ** [액션] 수정 버튼 핸들러 **
  const handleEditDesc = (e) => {
    const { value } = e.target;
    dispatch(
      handleSetRagState({
        type: 'info',
        info: {
          ...info,
          description: value,
        },
      }),
    );
  };

  // chunk count handler
  const onChangeChunk = (value) => {
    setChunkCount(value);
  };

  // list 클릭
  const onClickEmbeddedModelList = (model, type) => {
    setEmbeddedModel((prev) => ({
      ...prev,
      // or ...initialModelData,
      selectedModel: model,
    }));
  };

  // file delete
  const onDeleteFileData = async () => {
    dispatch();
  };

  // file upload data modal
  const onClickUpload = () => {
    dispatch(
      openModal({
        modalType: 'RAG_FILE_UPLOAD',
        modalData: {
          workspaceId,
          modelId,
          refresh: () => {},
        },
      }),
    );
  };

  const onEditDesc = async () => {
    const res = await putRagDescription({ ragId: modelId, description });

    const { status, result, message, error } = res;
    if (status === STATUS_SUCCESS) {
    } else {
      errorToastMessage(error, message);
    }

    setIsDescription(false);
  };

  // embedded sub menu 클릭
  const onClickSubMenu = async (selectedItem) => {
    setEmbeddedModel((prev) => ({
      ...prev,
      selectedOption: selectedItem,
    }));
  };

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  const infoData = useMemo(
    () => [
      { label: '설명', value: info.description || '-' },
      { label: '생성자', value: info.owner || '-' },
      { label: '생성 일시', value: info.create_datetime || '-' },
      { label: '최근 업데이트 일시', value: info.update_datetime || '-' },
    ],
    [info.create_datetime, info.description, info.owner, info.update_datetime],
  );

  const breadCrumbHandler = useCallback(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'rag',
          },
        },
      ]),
    );
  }, [dispatch]);

  useEffect(() => {
    loadModalComponent('RAG_EMBEDDING_MODAL');
    loadModalComponent('RAG_FILE_UPLOAD');
    breadCrumbHandler();
  }, [breadCrumbHandler]);

  return (
    <div className={cx('container')}>
      <div className={cx('input')}>
        <div className={cx('left')}>
          <div
            className={cx('left-top', rag?.status === 'creating' && 'disabled')}
          >
            <div className={cx('title')}>정보</div>
            {infoData.map((item, index) => (
              <div className={cx('info')} key={index}>
                <div className={cx('label')}>
                  <div className={cx('desc')}>
                    {item.label}
                    {index === 0 && !isDescription && (
                      <img
                        className={cx('img')}
                        src='/images/icon/00-ic-basic-pen.svg'
                        alt='edit'
                        // style={{
                        //   opacity: item.value ? 1 : 0.2,
                        // }}
                        onClick={() => {
                          setIsDescription(true);
                          // onUpdateDesc(item);
                        }}
                      />
                    )}
                  </div>
                  {index === 0 && isDescription && (
                    <ButtonV2
                      label={t('update.label')}
                      colorType='skyblue'
                      onClick={onEditDesc}
                    />
                  )}
                </div>

                {index === 0 && isDescription && (
                  <Textarea
                    size='large'
                    placeholder={t('llm.rag.add.desc.placeholder')}
                    value={info.description}
                    name='description'
                    onChange={(e) => handleEditDesc(e)}
                    customStyle={{
                      fontSize: '14px',
                      display: !isDescription && 'none',
                    }}
                  />
                )}

                <div
                  className={cx('value')}
                  style={{
                    display: index === 0 && isDescription && 'none',
                  }}
                >
                  {item.value}
                </div>
              </div>
            ))}
          </div>
          {rag && rag.status === 'creating' && (
            <RagInstance instanceInfo={instance} />
          )}
        </div>
        <RagSettingCenter
          onDeleteFileData={onDeleteFileData}
          onClickUpload={onClickUpload}
          onChangeChunk={onChangeChunk}
          embeddedList={embeddedList}
          embeddedModel={embeddedModel}
          onClickList={onClickEmbeddedModelList}
          openRagModelModal={openRagModelModal}
          chunkCount={chunkCount}
          onClickSubMenu={onClickSubMenu}
          reranker={reranker}
          status={status}
          t={t}
        />
      </div>
      <RagSettingRight />
    </div>
  );
});

export default RagSetting;
