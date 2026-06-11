import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2, InputText } from '@tango/ui-react';

import { postPlaygroundTestChat } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import flightBaseIcon from '/public/images/favicon/android-icon-36x36.png';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptCom.module.scss';

const cx = classNames.bind(style);

const PromptText = ({ type, message = '', handleScrollBottom }) => {
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const sliceName = userName.slice(0, 2);

  useEffect(() => {
    handleScrollBottom();
  }, [handleScrollBottom]);

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
    const { output } = result[0];
    setChatList((prev) => {
      const arr = [...prev];
      arr.push({
        type: 'output',
        message: output,
      });
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

  const session_id = sessionStorage.getItem('loginedSession');

  const handleInputCick = async () => {
    if (!input) return;
    if (isLoading) return;

    setChatList((prev) => {
      const arr = [...prev];
      arr.push({
        type: 'input',
        message: input,
      });
      return arr;
    });
    setInput('');

    const body = {
      playground_id: playgroundId,
      test_type: 'question',
      test_question: input,
      session_id,
    };

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
            />
          );
        })}
      </div>
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
