import { ButtonV2 } from '@jonathan/ui-react';

import {
  deleteRagDeployment,
  postRagDocuments,
  postRagSetting,
} from '@src/apis/llm/rag';
import { loadModalComponent } from '@src/modal';
import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';
import WarningIcon from '@src/static/images/icon/ic-warning-yellow.svg';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { handleSetRagState } from '@src/store/modules/llmRag';
import { openModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import useSSESearchStatus from '../RagContent/RagSearch/useSSESearchStatus';
import useSSESettingStatus from '../RagContent/useSSESettingStatus';

import classNames from 'classnames/bind';
import style from './RagHeader.module.scss';

const cx = classNames.bind(style);

export const uploadFiles = async ({ files, ragId }) => {
  const res = await postRagDocuments({ files, ragId });

  const { status, result, error, message } = res;
  if (status === STATUS_SUCCESS) {
    console.log('File upload ok');
  }
};

// 설정 - 저장
export const onClickSave = async ({
  docList,
  ragId,
  chunkLen,
  embeddingModel,
  embeddingToken,
  rerankerModel,
  rerankerToken,
  setSettingSaveLoading,
}) => {
  if (setSettingSaveLoading) {
    setSettingSaveLoading(true);
  }

  const oldFiles = []; // 기존에get으로 받은 id
  const newFiles = []; // 새로운 file객체, id 값이 없으니 name으로
  const fileObj = []; // 진짜로 업로드 api에 보낼 찐 File객체

  docList.forEach((item) => {
    if (item instanceof File) {
      newFiles.push(item.name);
      fileObj.push(item);
    } else if (item.id !== undefined) {
      oldFiles.push(item.id);
    }
  });
  const res = await postRagSetting({
    ragId,
    chunk: chunkLen,
    embeddingId: embeddingModel,
    embeddingToken,
    rerankerId: rerankerModel,
    rerankerToken,
    oldFiles, // 이전 파일
    newFiles, // 새로운 파일 - 우선 name만 미리 보낸다.
  });

  const { result, error, message, status } = res;

  if (status === STATUS_SUCCESS) {
    if (fileObj.length > 0) {
      await uploadFiles({ files: fileObj, ragId });
    }
  } else {
    errorToastMessage(error, message);
  }
  if (setSettingSaveLoading) {
    setSettingSaveLoading(false);
  }
};

// ** 검색 시스템 로그 버튼 활성화 여부
const calIsSettingSystemLogBtn = (setting, rerankerSwitch, rag, doc) => {
  if (!setting || !rag || !doc) return true;
  const {
    chunk_len: chunk,
    doc_list: docList,
    embedding_model: embedding,
    reranker_model: reranker,
  } = setting;

  if (!docList || docList.length < 1) {
    return true;
  }
  if (!chunk || chunk === 0) return true;
  if (!embedding) return true;
  // reranker 스위치가 켜져있으면서 데이터가 없으면 뿌린다
  if (rerankerSwitch && !reranker) return true;

  const { status: ragStatus, data: ragData } = rag;
  const { status: docStatus, success: docSuccess, total: docTotal } = doc;

  // ** ragStatus
  // stop,

  // 업로드중입니다
  if (docStatus === 'uploading') {
    return false;
  }
  //생성 버튼 클릭하세요
  if (ragStatus === 'stop') return true;

  if (ragStatus === 'creating') return false;
  return false;
};

// ** 검색 생성 버튼 활성화 여부
const calIsSettingCreateBtn = (setting, rerankerSwitch, rag, doc) => {
  if (!setting || !rag || !doc) return true;
  const {
    chunk_len: chunk,
    doc_list: docList,
    embedding_model: embedding,
    reranker_model: reranker,
  } = setting;

  if (!docList || docList.length < 1) {
    return true;
  }
  if (!chunk || chunk === 0) return true;
  if (!embedding) return true;
  // reranker 스위치가 켜져있으면서 데이터가 없으면 뿌린다
  if (rerankerSwitch && !reranker) return true;

  /// 다 통과 하면 , 갖춰야ㅕ할 것들은 다 갗군거고

  const { status: ragStatus, data: ragData } = rag;
  const { status: docStatus, success: docSuccess, total: docTotal } = doc;

  // ** ragStatus
  // stop,

  // 업로드중입니다
  if (docStatus === 'uploading') {
    return true;
  }
  //생성 버튼 클릭하세요
  if (ragStatus === 'stop') return false;

  if (ragStatus === 'creating') return true;

  return false;
};

// ** [계산] 검색 중지 버튼
const calIsSearchStopBtn = (searchStatus) => {
  if (!searchStatus) return true;
  const { status } = searchStatus;

  if (status === 'stop') return true;
  return false;
};

// ** [계산] 검색 중지 버튼 visible
const calIsSearchStopVisible = (searchStatus) => {
  if (!searchStatus) return false;
  const { status } = searchStatus;

  if (status === 'stop') return false;
  return true;
};

// ** [계산] 검색 저장 버튼
const calIsSettingSaveBtn = (ragStatus, docStatus) => {
  if (!ragStatus || !docStatus) return true;

  if (ragStatus === 'creating') return true;
  return false;
};

// ** [계산] 검색 테스트 버튼 visible
const calIsTestBtnVisible = (ragStatus) => {
  const { status } = ragStatus || { status: null };

  if (status === 'installing' || status === 'pending') return false;
  return true;
};

// ** [계산] 설정 - 재생성 버튼으로 변경
const calIsSettingReCreateBtn = () => {};

// ** [계산] Search - 버튼 옆 메시지 출력 **
const calSearchHeaderMessage = (searchStatus) => {
  // fetching 추가
  if (!searchStatus) return { color: '', message: '', img: null };

  const { status } = searchStatus;

  switch (status) {
    case 'installing':
      return {
        color: '#00c775 ',
        message: 'llm.rag.search.installing.status.message',
        img: null,
      };
    case 'pending':
      return {
        color: '#ff7a00',
        message: 'llm.rag.search.pending.status.message',
        img: null,
      };
    case 'stop':
      return {
        color: '#fa4e57',
        message: 'llm.rag.search.stop.status.message',
        img: null,
      };
    case 'running':
      return {
        color: '#2d76f8',
        message: 'llm.rag.search.stop.status.message',
        img: null,
      };
    case 'error':
      return {
        color: '#fa4e57',
        message: 'llm.rag.search.error.status.message',
        img: WarningIcon,
      };
    default:
      return { color: '', message: '', img: null };
  }
};

// ** [계산] 검색 시스템 로그 버튼
const calIsSearchSystemLogBtn = (searchStatus) => {
  if (!searchStatus) return true;
  const { status } = searchStatus;

  if (status === 'stop') return true;
  return false;
};

// ** [계산] 헤더 메세지 계산 함수 **
const calHeaderMessage = (projectTemplate, serverProjectTemplate) => {
  const { system_message, user_message } = projectTemplate;
  const { server_system_message, server_user_message } = serverProjectTemplate;

  if (
    !server_system_message &&
    !server_user_message &&
    !system_message &&
    !user_message
  )
    return '';

  if (
    server_system_message !== system_message ||
    server_user_message !== user_message
  )
    return '변경 사항을 적용하시려면 커밋 버튼을 클릭해 주세요.';
  if (!system_message || !user_message) return '프롬프트를 입력해 주세요.';
  return '';
};

// ** 중지 핸들러
const handleStop = async (dispatch, ragId, type) => {
  if (type === 'test') {
    dispatch(
      handleSetRagState({
        type: 'searchOutput',
        searchOutput: null,
      }),
    );
  }
  const res = await deleteRagDeployment({ ragId, type });

  const { reslt, message, error, status } = res;

  if (status === STATUS_SUCCESS) {
  } else {
    errorToastMessage(error, message);
  }
};

// ** [액션] 뒤로가기 핸들러 **
export const handleBackGo = (history) => {
  history.go(-1);
};

export default function RagHeader({ selectedTab }) {
  const history = useHistory();
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { id: workspaceId, rid: ragId } = match.params;
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const [settingSaveLoading, setSettingSaveLoading] = useState(false);

  const { setting, instance, rerankerSwitch, info } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );
  const [settingStatus, setSettingStatus] = useState(null);
  const [searchStatus, setSearchStatus] = useState(null);

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

  // ** 버튼 활성화 여부 **
  const isSearchStopBtn = calIsSearchStopBtn(searchStatus);
  const isSearchStopBtnVisible = calIsSearchStopVisible(searchStatus);
  const isSearchSystemLogBtn = calIsSearchSystemLogBtn(searchStatus);
  const isSettingSaveBtn = calIsSettingSaveBtn(ragStatus, docStatus);
  const isTestBtnVisible = calIsTestBtnVisible(searchStatus);
  const insSettingCreateBtn = calIsSettingCreateBtn(
    setting,
    rerankerSwitch,
    rag,
    docs,
  );
  const isSettingSystemLogBtn = calIsSettingSystemLogBtn(
    setting,
    rerankerSwitch,
    rag,
    docs,
  );
  const isSettingVisibleStopBtn = ragStatus === 'creating';

  // ** Search - 버튼 옆 메시지 **
  const {
    color: searchHeaderColor,
    message: searchHeaderMessage,
    img,
  } = calSearchHeaderMessage(searchStatus);

  const { id, name, owner } = info || { id: 0, name: '-', owner: '-' };

  const {
    chunk_len: chunkLen,
    doc_list: docList,
    embedding_model: embeddingModel,
    reranker_model: rerankerModel,
    embedding_token: embeddingToken,
    reranker_token: rerankerToken,
  } = setting;

  // 시스템 로그
  const onClickSystemLog = (type) => {
    dispatch(
      openModal({
        modalType: 'RAG_SYSTEM_LOG',
        modalData: {
          workspaceId,
          ragId,
          // git: fineTuningData?.huggingface_git,
          onSubmit: (e) => {},
          refresh: () => {},
          ragType: type,
        },
      }),
    );
  };

  useSSESettingStatus(ragId, userName, setSettingStatus, info);
  useSSESearchStatus(ragId, userName, setSearchStatus, info);

  useEffect(() => {
    if (searchStatus) {
      dispatch(
        handleSetRagState({
          type: 'searchStatus',
          searchStatus,
        }),
      );
    }
  }, [searchStatus, dispatch]);

  useEffect(() => {
    if (settingStatus) {
      dispatch(
        handleSetRagState({
          type: 'settingStatus',
          settingStatus,
        }),
      );
    }
  }, [settingStatus, dispatch]);

  // 생성
  const onClickDeployment = (urlType) => {
    dispatch(
      openModal({
        modalType: 'RAG_TEST_MODAL',
        modalData: {
          workspaceId,
          ragId,
          // git: fineTuningData?.huggingface_git,
          onSubmit: ({ instanceId, instanceCount, gpuCount }) => {
            // return runFineTuning({ instanceId, instanceCount, gpuCount });
          },
          urlType,
          // refresh: () => getFineTuningData(),
        },
      }),
    );
  };

  useEffect(() => {
    loadModalComponent('RAG_SYSTEM_LOG');
    loadModalComponent('RAG_SETTING_CREATE_MODAL');
    loadModalComponent('RAG_TEST_MODAL');
  }, []);

  return (
    <div className={cx('header-cont')}>
      <div className={cx('back-btn')} onClick={() => handleBackGo(history)}>
        <img src={BackIcon} alt='back-icon' />
        <span>RAG</span>
      </div>
      <div className={cx('header-content-cont')}>
        <div className={cx('title-cont')}>
          {/* <h2 className={cx('header-title')}>{displayName}</h2>
          <span className={cx('commit-txt')}>{commitName}</span> */}
          <h2 className={cx('header-title')}>{name}</h2>
          {/* <span className={cx('commit-txt')}>{owner}</span> */}
        </div>
        {selectedTab === 0 && (
          <div className={cx('header-content-right')}>
            {/* <p className={cx('error-message-paragraph')}>{headerMessage}</p> */}
            {/* <p className={cx('error-message-paragraph')}>status text</p> */}
            <ButtonV2
              colorType='skyblue'
              label={t('systemLog.label')}
              disabled={isSettingSystemLogBtn}
              onClick={() => onClickSystemLog('retrieval')}
            />
            <ButtonV2
              colorType='skyblue'
              label={t('saveBtn.label')}
              isLoading={settingSaveLoading || docStatus === 'uploading'}
              disabled={isSettingSaveBtn}
              onClick={() => {
                if (!settingSaveLoading && docStatus !== 'uploading') {
                  onClickSave({
                    docList,
                    ragId,
                    chunkLen,
                    embeddingModel,
                    embeddingToken,
                    rerankerModel,
                    rerankerToken,
                    setSettingSaveLoading,
                  });
                }
              }}
            />
            {!isSettingVisibleStopBtn ? (
              <ButtonV2
                label={t('create.label')}
                disabled={insSettingCreateBtn}
                onClick={() => onClickDeployment('retrieval')}
              />
            ) : (
              <ButtonV2
                colorType='red'
                label={t('stop.label')}
                onClick={() => handleStop(dispatch, ragId, 'retrieval')}
              />
            )}
          </div>
        )}
        {selectedTab === 1 && (
          <div className={cx('header-content-right')}>
            {/* <p className={cx('error-message-paragraph')}>{headerMessage}</p> */}
            <p
              className={cx('error-message-paragraph')}
              style={{ searchHeaderColor }}
            >
              {img && (
                <img
                  src={img}
                  alt='warning-icon'
                  style={{ marginRight: '8px' }}
                />
              )}
              {t(searchHeaderMessage)}
            </p>
            <ButtonV2
              colorType='skyblue'
              label={t('systemLog.label')}
              disabled={isSearchSystemLogBtn}
              onClick={() => onClickSystemLog('test')}
            />
            {isTestBtnVisible && (
              <ButtonV2
                label={t('test.label')}
                onClick={() => onClickDeployment('test')}
              />
            )}

            {isSearchStopBtnVisible && (
              <ButtonV2
                colorType='red'
                label={t('stop.label')}
                disabled={isSearchStopBtn}
                onClick={() => handleStop(dispatch, ragId, 'test')}
              />
            )}
            {/* <ButtonV2
              colorType='red'
              label={t('stop.label')}
              onClick={() => handleStop(ragId, ''retrieval')}
            /> */}
          </div>
        )}
      </div>
    </div>
  );
}
