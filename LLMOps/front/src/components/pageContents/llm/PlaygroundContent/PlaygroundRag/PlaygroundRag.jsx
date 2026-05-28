import { ButtonV2, Switch } from '@jonathan/ui-react';

import IconClose from '@src/static/images/icon/00-ic-black-close.svg';
import DisabledCloseIcon from '@src/static/images/icon/delete-x-gray.svg';
import IconHugginFace from '@src/static/images/icon/hugging-face.svg';
import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import {
  handleSetPlaygroundState,
  handleSetRagValue,
  initialLLMPlaygroundState,
} from '@src/store/modules/llmPlayground';
import { openModal } from '@src/store/modules/modal';

import { convertByte } from '@src/utils';

import PlaygroundAccordion from '../PlaygroundAccordion';
import PlaygroundFrame from '../PlaygroundFrame';
import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';
import PlaygroundRangeBar from '../PlaygroundRangeBar';
import PlaygroundTooltip from '../PlaygroundTooltip';

import classNames from 'classnames/bind';
import style from './PlaygroundRag.module.scss';

const cx = classNames.bind(style);

const PlaygroundRag = React.memo(({ workspaceId, playgroundId }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const {
    is_rag,
    rag_id,
    rag_name,
    chunk_len,
    chunk_max,
    docs_total_count,
    docs_total_size,
    embedding_huggingface_model_id,
    reranker_huggingface_model_id,
  } = useSelector((state) => state.llmPlayground.rag, shallowEqual);

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isDisabled = calIsDeployLoading(statusType);

  const documentSize = convertByte(docs_total_size);
  const chunckLengthTooltipContents = t(
    'playground.chunk.length.tooltip',
  ).split('\n');

  const handleRangeBar = useCallback(
    (e) => {
      dispatch(
        handleSetRagValue({
          type: 'chunk_max',
          ragValue: e.target.value,
        }),
      );
    },
    [dispatch],
  );

  const handelSwitch = useCallback(() => {
    dispatch(
      handleSetRagValue({
        type: 'is_rag',
        ragValue: !is_rag,
      }),
    );
  }, [dispatch, is_rag]);

  const handleOpenRagImport = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'IMPORT_RAG',
        modalData: {
          workspaceId,
          playgroundId,
        },
      }),
    );
  }, [dispatch, playgroundId, workspaceId]);

  const handleDeleteRag = useCallback(() => {
    dispatch(
      handleSetPlaygroundState({
        type: 'rag',
        rag: initialLLMPlaygroundState.rag,
      }),
    );
  }, [dispatch]);

  return (
    <PlaygroundFrame>
      <div className={cx('flex-32')}>
        <div className={cx('header')}>
          <h3 className={cx('title')}>RAG</h3>
          <Switch
            name='playgroundRag'
            onChange={handelSwitch}
            checked={is_rag || rag_name}
            disabled={!!rag_name}
          />
        </div>
        {!rag_id && (
          <ButtonV2
            label={`RAG ${t('getInfo.label')}`}
            type='outline'
            size='m'
            style={{
              width: '100%',
              marginBottom: '32px',
            }}
            disabled={!is_rag}
            onClick={handleOpenRagImport}
          />
        )}
        {rag_id && (
          <>
            <div className={cx('selected-rag-cont', isDisabled && 'disabled')}>
              <span className={cx('rag-name-txt', isDisabled && 'disabled')}>
                {rag_name}
              </span>
              <button
                className={cx('rag-delete-btn')}
                onClick={handleDeleteRag}
              >
                <img
                  src={isDisabled ? DisabledCloseIcon : IconClose}
                  alt='close-btn-img'
                />
              </button>
            </div>
            <div className={cx('border')}></div>
            <PlaygroundRangeBar
              label={t('llm.rag.searchResult.label')}
              value={chunk_max}
              min={0}
              max={100}
              disabled={isDisabled}
              tooltipContent={t('playground.max.chunk.tooltip')}
              onChange={handleRangeBar}
            />
            <div className={cx('rag-info-cont')}>
              <div className={cx('flex-32')}>
                <div className={cx('flex-16')}>
                  <span className={cx('rag-info-label')}>
                    {t('docs.label')}
                  </span>
                  <PlaygroundAccordion />
                </div>
                <div className={cx('flex-16')}>
                  <span className={cx('rag-info-label')}>
                    {t('docs.label')} {t('count.column.label')}
                  </span>
                  <span className={cx('rag-info-value')}>
                    {docs_total_count}
                  </span>
                </div>
                <div className={cx('flex-16')}>
                  <span className={cx('rag-info-label')}>
                    {t('docs.label')} {t('data.size.label')}
                  </span>
                  <span className={cx('rag-info-value')}>{documentSize}</span>
                </div>
                <div className={cx('flex-16')}>
                  <div className={cx('chunk-length-cont')}>
                    <span className={cx('rag-info-label')}>
                      {t('chunk.length.label')}
                    </span>
                    <PlaygroundTooltip
                      content={
                        <div
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                          }}
                        >
                          <span>{chunckLengthTooltipContents[0]}</span>
                          <span>{chunckLengthTooltipContents[1]}</span>
                        </div>
                      }
                    />
                  </div>
                  <span className={cx('rag-info-value')}>{chunk_len}</span>
                </div>
                <div className={cx('flex-16')}>
                  <span className={cx('rag-info-label')}>
                    {t('ragEmbeddedModel.label')}
                  </span>
                  <div className={cx('imbeding-model-cont')}>
                    <img src={IconHugginFace} alt='hugging-face-icon' />
                    <span className={cx('hugging-txt')}>Hugging Face</span>
                    <span className={cx('rag-info-value')}>
                      {embedding_huggingface_model_id}
                    </span>
                  </div>
                </div>
                {reranker_huggingface_model_id && (
                  <div className={cx('flex-16')}>
                    <span className={cx('rag-info-label')}>
                      {t('ragRerankerModel.label')}
                    </span>
                    <div className={cx('imbeding-model-cont')}>
                      <img src={IconHugginFace} alt='hugging-face-icon' />
                      <span className={cx('hugging-txt')}>Hugging Face</span>
                      <span className={cx('rag-info-value')}>
                        {reranker_huggingface_model_id}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </PlaygroundFrame>
  );
});

export default PlaygroundRag;
