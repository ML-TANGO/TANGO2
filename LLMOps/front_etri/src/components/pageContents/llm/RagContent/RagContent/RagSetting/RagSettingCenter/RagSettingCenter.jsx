import { ButtonV2, InputNumber, Switch } from '@tango/ui-react';

import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import CloseIcon from '@src/static/images/icon/00-ic-black-close.svg';
import DisabledCloseIcon from '@src/static/images/icon/delete-x-gray.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';
import { useRef, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import { handleSetRagState } from '@src/store/modules/llmRag';
import TooltipPortal from '@src/hooks/TooltipPortal';

import RagDocList from './RagDocList';

import classNames from 'classnames/bind';
import style from './RagSettingCenter.module.scss';

const cx = classNames.bind(style);

const noSelectedDataMessage = {
  first: 'commitVersion.message',
};

const title = {
  first: 'commit.label',
};

const radioTypeOptions = [
  {
    label: 'notUsed.label',
    value: 1,
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
  {
    label: 'used.label',
    value: 0,
    labelStyle: {
      fontSize: '14px',
      fontFamily: 'SpoqaM',
      marginTop: '2px',
    },
  },
];

const docListCheck = (setting) => {
  if (!setting || !setting?.doc_list) {
    return true;
  }
  if (
    typeof setting.doc_list === 'object' &&
    Object.keys(setting.doc_list).length === 0
  ) {
    return true;
  }
  return false;
};

function RagSettingCenter({
  onDeleteFileData,
  onClickUpload,
  onChangeChunk,
  chunkCount,
  onClickList,
  embeddedList,
  embeddedModel,
  getEmbedded,
  onClickSubMenu,
  openRagModelModal,
  status,
  reranker,
  t,
}) {
  const dispatch = useDispatch();
  const [isDescription, setIsDescription] = useState(false);
  const [isDisabled, setIsDisabled] = useState(false);
  const tooltipRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  const { setting, info, instance, rerankerSwitch, settingStatus } =
    useSelector((state) => state.llmRag, shallowEqual);

  const { rag, docs } = settingStatus || { rag: null, docs: null };

  const { status: ragStatus, data: ragData } = rag || {
    status: null,
    data: null,
  };

  const {
    reranker_model: rerankerModel,
    doc_list: docList,
    embedding_model: embeddingModel,
    chunk_len: chunkLen,
  } = setting;
  const [selectedFile, setSelectedFile] = useState([]);

  // 문서 제거
  const onDeleteDoc = () => {
    const prevDocList = docList || [];
    const newFiles = prevDocList.filter(
      (file) => !selectedFile.includes(file.name),
    );

    dispatch(
      handleSetRagState({
        type: 'setting',
        setting: {
          ...setting,
          doc_list: newFiles,
        },
      }),
    );
  };

  const handelSwitch = (e) => {
    dispatch(
      handleSetRagState({
        type: 'rerankerSwitch',
        rerankerSwitch: !rerankerSwitch,
      }),
    );
  };

  // 문서 체크박스
  const handleFileCheckbox = (id) => {
    setSelectedFile((prevSelectedId) => {
      if (prevSelectedId.includes(id)) {
        return prevSelectedId.filter((selectedId) => selectedId !== id);
      } else {
        return [...prevSelectedId, id];
      }
    });
  };

  // 최대 청크 수 핸들러
  const handleChunkCount = (value) => {
    dispatch(
      handleSetRagState({
        type: 'setting',
        setting: {
          ...setting,
          chunk_len: value,
        },
      }),
    );
  };

  const handleDeleteModel = (type) => {
    const model = {};
    if (type === 'embedding') {
      model.embedding_model = null;
    } else {
      model.reranker_model = null;
    }
    dispatch(
      handleSetRagState({
        type: 'setting',
        setting: {
          ...setting,
          ...model,
        },
      }),
    );
  };
  return (
    <div className={cx('container', ragStatus === 'creating' && 'disabled')}>
      <div className={cx('title')}> {`RAG ${t('setting.label')}`}</div>
      <div className={cx('file')}>
        <div className={cx('sub-title')}>{t('docs.label')}</div>
        {docListCheck(setting) ? (
          <ButtonV2 // 추가
            type='outline'
            size='l'
            label={t('docs.upload.label')}
            // disabled={disabled}
            onClick={onClickUpload}
            style={{ width: '100%', height: '34px' }}
          />
        ) : (
          <RagDocList
            // list={testData}
            // list={setting.doc_list.map((doc) => ({ file_name: doc.name }))}
            list={docList ?? []}
            selectedList={selectedFile}
            handleCheckbox={handleFileCheckbox}
            disable={ragStatus === 'creating'}
            onClickLeft={onDeleteDoc}
            onClickRight={onClickUpload}
            t={t}
          />
        )}
      </div>

      <div className={cx('chunk')}>
        <div className={cx('sub-title')}>
          {t('chunk.length.label')}

          <img
            ref={tooltipRef}
            src={InfoIcon}
            alt='tooltip-icon'
            onMouseEnter={() => setIsShowTooltip(true)}
            onMouseLeave={() => setIsShowTooltip(false)}
          />
          <TooltipPortal
            direction='bottom'
            targetRef={tooltipRef}
            isShowTooltip={isShowTooltip}
          >
            <DarkTooltip
              direction='bottom'
              tooltipColor='#c1c1c1'
              content={
                <div
                  style={{
                    display: 'flex',
                    minWidth: '32px',
                    fontFamily: 'SpoqaM',
                    fontSize: '10px',
                    justifyContent: 'center',
                    color: '#fff',
                  }}
                >
                  {t('llm.rag.chunk.tooltip.message')}
                </div>
              }
            />
          </TooltipPortal>
        </div>
        <InputNumber // ! 최대 청크 수
          name='ragChunk'
          placeholder={`${t('currentAvailableCount')}`}
          isDisabled={ragStatus === 'creating'}
          min={0}
          max={1000}
          value={chunkLen}
          disableIcon
          customSize={{ hieght: '34px' }}
          onChange={(e) => {
            let inputValue = e.value;
            handleChunkCount(inputValue);
          }}
        />
      </div>

      <div className={cx('embedded')}>
        <div className={cx('sub-title')}>{t('ragEmbeddedModel.label')}</div>

        {embeddingModel ? (
          <div
            className={cx('model-box', ragStatus === 'creating' && 'disabled')}
          >
            <div>
              <img src={IconSmile} alt='icon' />
              {embeddingModel}
            </div>
            <img
              src={isDisabled ? DisabledCloseIcon : CloseIcon}
              alt='close-icon'
              onClick={() => {
                if (ragStatus !== 'creating') {
                  handleDeleteModel('embedding');
                }
              }}
              className={cx('close')}
            />
          </div>
        ) : (
          <ButtonV2 // 추가
            type='outline'
            size='l'
            label={t('llm.rag.select.model.label')}
            disabled={ragStatus === 'creating'}
            onClick={() => {
              if (ragStatus !== 'creating') {
                openRagModelModal('embedding');
              }
            }}
            style={{ width: '100%', height: '34px' }}
          />
        )}
      </div>

      <div className={cx('reranker')}>
        <div className={cx('sub-title', 'flex')}>
          {t('ragRerankerModel.label')}
          <Switch
            name='playgroundRag'
            onChange={(e) => handelSwitch(e)}
            checked={rerankerModel || rerankerSwitch}
            disabled={!!rerankerModel || ragStatus === 'creating'}
          />
        </div>
        <div className={cx('reranker')}>
          {rerankerModel && (
            <div
              className={cx(
                'model-box',
                ragStatus === 'creating' && 'disabled',
              )}
            >
              <div>
                <img src={IconSmile} alt='icon' />
                {rerankerModel}
              </div>
              <img
                src={isDisabled ? DisabledCloseIcon : CloseIcon}
                alt='close-icon'
                onClick={() => handleDeleteModel('reranker')}
                className={cx('close')}
              />
            </div>
          )}
          {!rerankerModel && rerankerSwitch && (
            <ButtonV2 // 추가
              type='outline'
              size='l'
              label={t('llm.rag.select.model.label')}
              disabled={ragStatus === 'creating'}
              onClick={() => openRagModelModal('reranker')}
              style={{ width: '100%' }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default RagSettingCenter;
