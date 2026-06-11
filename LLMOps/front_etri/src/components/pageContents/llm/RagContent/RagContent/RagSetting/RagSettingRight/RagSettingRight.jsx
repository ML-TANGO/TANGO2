import { Emptybox, Loading } from '@tango/ui-react';

import WarningIcon from '@src/static/images/icon/ic-warning-yellow.svg';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import classNames from 'classnames/bind';
import style from './RagSettingRight.module.scss';

const cx = classNames.bind(style);

// ** [계산] 설정 상태 및 데이터 별 메시지
const calIsMessage = (setting, rerankerSwitch, rag, doc, t) => {
  if (!setting || !rag || !doc) return <Loading />;
  const {
    chunk_len: chunk,
    doc_list: docList,
    embedding_model: embedding,
    reranker_model: reranker,
  } = setting;

  const { status: ragStatus, data: ragData } = rag;
  // const ragStatus = 'error';
  // const ragData = null;
  const { status: docStatus, success: docSuccess, total: docTotal } = doc;

  if (ragStatus === 'created' && ragData) return '';

  if (ragStatus === 'error')
    return (
      <>
        <img
          src={WarningIcon}
          alt='error-icon'
          style={{ widht: '16px', height: '16px', marginRight: '8px' }}
        />
        {t('llm.rag.setting.create.error.message')}
      </>
    );
  // ** ragStatus
  // stop,

  // 업로드중입니다
  if (docStatus === 'uploading') {
    return (
      <div className={cx('uploading')}>
        <span>{t('llm.rag.setting.uploading.message')}</span>
        <span>{`${t('progressStatus')}: ${t('ea.label', {
          count: docSuccess,
        })} / ${t('ea.label', { count: docTotal })}`}</span>
      </div>
    );
  }

  if (!docList || docList.length < 1) {
    return t('llm.rag.setting.noDataList.message');
  }
  if (!chunk || chunk === 0) return t('llm.rag.setting.noChunk.message');
  if (!embedding) return t('llm.rag.setting.noEmbedding.message');
  // reranker 스위치가 켜져있으면서 데이터가 없으면 뿌린다
  if (rerankerSwitch && !reranker)
    return t('llm.rag.setting.noReranker.message');

  //생성 버튼 클릭하세요
  if (ragStatus === 'stop') return t('llm.rag.setting.create.message');

  if (ragStatus === 'creating') return t('llm.rag.setting.creating.message');

  return '';
};

function RagSettingRight({ list, loading }) {
  const { t } = useTranslation();
  const [prevGraphData, setPrevGraphData] = useState([]);
  const { setting, info, instance, settingStatus, rerankerSwitch } =
    useSelector((state) => state.llmRag, shallowEqual);

  const { rag, docs } = settingStatus || { rag: null, docs: null };

  const { status: ragStatus, data: ragData } = rag || {
    status: null,
    data: null,
  };
  const {
    status: docStatus,
    success: docSuccess,
    total: docTotal,
  } = docs || { status: null, success: null, total: null };

  const message = calIsMessage(setting, rerankerSwitch, rag, docs, t);

  const formatNumber = (number) => {
    return `# ${String(number).padStart(3, '0')}`;
  };
  // useEffect(() => {
  //   if (!ragData) return;
  //   setPrevGraphData((prevState) => {
  //     if (prevState.length !== ragData.length) {
  //       return [];
  //     }

  //     const isDifferent = prevState.some((prevItem, index) => {
  //       const newItem = ragData[index];
  //       return prevItem.id !== newItem.id;
  //     });

  //     return isDifferent ? ragData : prevState;
  //   });
  // }, [ragData]);

  return (
    <div
      className={cx(
        'container',
        ragStatus === 'creating' && 'disabled',
        ragStatus === 'error' && 'error',
      )}
    >
      {!ragData && <div className={cx('message')}>{message}</div>}

      {(ragStatus === 'completed' || ragStatus === 'stop') &&
        ragData &&
        ragData.map(({ character, content }, i) => {
          return (
            <div className={cx('item')}>
              <div className={cx('top')}>
                <div>{formatNumber(i + 1)}</div>
                <div>{character}</div>
              </div>
              <div className={cx('bottom')}>{content}</div>
            </div>
          );
        })}
    </div>
  );
}

export default RagSettingRight;
