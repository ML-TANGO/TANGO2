import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2, InputText } from '@jonathan/ui-react';

import {
  getPlayground,
  postPlaygroundTestChat,
} from '@src/apis/llm/playground';
import { SHOW_DUAL_DEPLOY } from '@src/featureFlags';
import { STATUS_SUCCESS } from '@src/network';

import flightBaseIcon from '/public/images/favicon/android-icon-36x36.png';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptCom.module.scss';

const cx = classNames.bind(style);

// 모달은 항상 워크스페이스 라우트(/user/workspace/:id/...) 안에서 열리므로 URL 에서 추출
// (PromptCom 까지 prop 스레딩 회피). 매치 실패 시 null → 이중모델 picker 옵션 비활성.
const getWorkspaceIdFromUrl = () => {
  const m = window.location.pathname.match(/\/workspace\/(\d+)/);
  return m ? m[1] : null;
};

const PromptText = ({ type, message = '', handleScrollBottom, t }) => {
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const sliceName = userName.slice(0, 2);

  useEffect(() => {
    handleScrollBottom();
  }, [handleScrollBottom]);

  // 이중모델: LLM1 이 재작성한 최적 프롬프트(답변 위에 캡션과 함께 표시).
  if (type === 'optimized') {
    return (
      <div className={cx('wrapper', 'output')}>
        <div
          className={cx('prompt-message-cont', 'output')}
          style={{ opacity: 0.85 }}
        >
          <div className={cx('img-cont')} />
          <div>
            <span style={{ fontSize: 11, color: '#2f6fed', fontWeight: 700 }}>
              ↳ {t('playground.dual.optimizedPrompt')}
            </span>
            <p className={cx('message-paragraph')} style={{ marginTop: 4 }}>
              {message}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cx('wrapper', type)}>
      <div className={cx('prompt-message-cont', type)}>
        <div className={cx('img-cont')}>
          {type === 'output' && (
            <img
              className={cx('user-img')}
              src={flightBaseIcon}
              alt='flightbase-icon'
            />
          )}
          {type === 'input' && (
            <span className={cx('username-txt')}>{sliceName}</span>
          )}
        </div>
        <p className={cx('message-paragraph')}>{message}</p>
      </div>
    </div>
  );
};

const handleInputTest = async (body, setIsLoading, setChatList) => {
  setIsLoading(true);
  const { result, status, message } = await postPlaygroundTestChat(body);
  if (status === STATUS_SUCCESS) {
    const { output, optimized_prompt: optimizedPrompt } = result[0];
    setChatList((prev) => {
      const arr = [...prev];
      // 이중모델 응답이면 최적 프롬프트(LLM1)를 답변(LLM2) 앞에 표시.
      if (optimizedPrompt && optimizedPrompt !== body.test_question) {
        arr.push({ type: 'optimized', message: optimizedPrompt });
      }
      arr.push({ type: 'output', message: output });
      return arr;
    });
  } else {
    toast.error(message);
  }
  setIsLoading(false);
};

export default function PromptCom({ playgroundId }) {
  const { t } = useTranslation();

  const [chatList, setChatList] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // 이중모델 추론(SP-7 슬라이스): LLM1(프롬프트 생성기)→LLM2(현 배포모델) 체인.
  const [dualEnabled, setDualEnabled] = useState(false);
  const [promptGenId, setPromptGenId] = useState('');
  const [genOptions, setGenOptions] = useState([]);
  // 1회 로드 센티넬 — genOptions.length 를 dep 으로 쓰면 빈 결과 시 매 렌더 재fetch 루프가 됨.
  const genFetchedRef = useRef(false);

  const session_id = sessionStorage.getItem('loginedSession');

  // 토글 ON 시 워크스페이스의 다른 playground 목록을 LLM1 후보로 로드(현재 것 제외). 1회만.
  useEffect(() => {
    if (!dualEnabled || genFetchedRef.current) return;
    const workspaceId = getWorkspaceIdFromUrl();
    if (!workspaceId) return;
    genFetchedRef.current = true;
    (async () => {
      const res = await getPlayground(workspaceId);
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result)
          ? res.result
          : (res.result?.list ?? []);
        setGenOptions(
          raw
            .map((p) => ({ id: p.id, name: p.name }))
            .filter(
              (p) => p.id != null && String(p.id) !== String(playgroundId),
            ),
        );
      } else {
        genFetchedRef.current = false; // 실패 시 재시도 허용
      }
    })();
  }, [dualEnabled, playgroundId]);

  const handleInputCick = async () => {
    if (!input) return;
    if (isLoading) return;
    if (dualEnabled && !promptGenId) {
      toast.error(t('playground.dual.selectGenerator'));
      return;
    }

    const question = input;
    setChatList((prev) => [...prev, { type: 'input', message: question }]);
    setInput('');

    const body = {
      playground_id: playgroundId,
      test_type: 'question',
      test_question: question,
      session_id,
    };
    if (dualEnabled && promptGenId) {
      body.prompt_gen_playground_id = promptGenId;
    }

    await handleInputTest(body, setIsLoading, setChatList);
  };

  const handleKeyEnter = (e) => {
    if (e.key !== 'Enter') return;
    handleInputCick();
  };

  const scrollRef = useRef(null);
  const handleScrollBottom = useCallback(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  return (
    <div className={cx('prompt-cont')}>
      <div className={cx('content-cont')} ref={scrollRef}>
        {chatList.map((el, idx) => {
          return (
            <PromptText
              key={idx}
              type={el.type}
              message={el.message}
              handleScrollBottom={handleScrollBottom}
              t={t}
            />
          );
        })}
      </div>

      {/* 이중모델 추론 컨트롤 — LLM1(프롬프트 생성기) 선택.
          SHOW_DUAL_DEPLOY 로 가린다: 같은 목적(프롬프트 개선)을 추론 화면 상단의
          프롬프트 최적화 토글이 대체하므로, 입력창에 두 갈래를 함께 두면 혼동된다.
          state·전송 경로는 그대로라 플래그만 되돌리면 복구된다(공인시험 데모). */}
      {SHOW_DUAL_DEPLOY && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '6px 4px',
            fontSize: 13,
          }}
        >
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
            }}
          >
            <input
              type='checkbox'
              checked={dualEnabled}
              onChange={(e) => setDualEnabled(e.target.checked)}
              disabled={isLoading}
            />
            {t('playground.dual.label')}
          </label>
          {dualEnabled && (
            <select
              value={promptGenId}
              onChange={(e) => setPromptGenId(e.target.value)}
              disabled={isLoading}
              style={{
                padding: '4px 8px',
                border: '1px solid #d8d8d8',
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              <option value=''>{t('playground.dual.selectGenerator')}</option>
              {genOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      <div className={cx('footer-cont')}>
        <div className={cx('input-cont')}>
          <InputText
            placeholder='프롬프트를 입력하세요.'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => handleKeyEnter(e)}
            isReadOnly={isLoading}
          />
        </div>
        <ButtonV2
          size='l'
          colorType='skyblue'
          label={t('input.label')}
          disabled={!input}
          isLoading={isLoading}
          onClick={handleInputCick}
        />
      </div>
    </div>
  );
}
