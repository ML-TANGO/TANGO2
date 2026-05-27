import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { t } from 'i18next';
import { CopyToClipboard } from 'react-copy-to-clipboard';
import { toast } from '@src/components/Toast';

import JonathanIcon from '@src/static/images/logo/ICO_Jonathan.svg';
import CopyIcon from '@src/static/images/icon/00-ic-basic-copy-o.svg';
import style from './LLMChatBox.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const MessageParagraph = ({
  text,
  type,
  isLastIndex,
  scrollBottom,
  setLoading,
}) => {
  const [displayText, setDisplayText] = useState('');
  const [textIndex, setTextIndex] = useState(0);

  // * 답변 타이핑 useEffect Hook
  useEffect(() => {
    if (type === 'input') {
      setDisplayText(text);
      return;
    }
    const typingInterval = setInterval(() => {
      if (type === 'output' && isLastIndex && textIndex < text.length) {
        setDisplayText((prevText) => prevText + text[textIndex]);
        setTextIndex((prevIndex) => prevIndex + 1);
        scrollBottom();
      } else {
        clearInterval(typingInterval);
      }
    }, 10);

    return () => clearInterval(typingInterval);
  }, [text, textIndex, type, isLastIndex, scrollBottom]);

  // * 답변이 끝난 후 loading false 처리
  useEffect(() => {
    if (textIndex !== text.length) return;
    setLoading(false);
  }, [textIndex, text, setLoading]);

  return <p className={cx('chat-paragraph')}>{displayText}</p>;
};

const LLMChatBox = ({ messageInfo, isLastIndex, scrollBottom, setLoading }) => {
  const { auth } = useSelector((state) => ({ auth: state.auth }));
  const { userName } = auth;
  const { type, message } = messageInfo;

  return (
    <div className={cx('chat-outer-box', type === 'output' && 'jonathan')}>
      <div className={cx('chat-img-box')}>
        {type === 'input' ? (
          <div className={cx('chat-profile-box')}>{userName.slice(0, 2)}</div>
        ) : (
          <div className={cx('fb-profile-box')}>
            <img
              className={cx('fb-profile-img')}
              src={JonathanIcon}
              alt='fb-profile-img'
            />
          </div>
        )}
        <MessageParagraph
          text={message}
          type={type}
          isLastIndex={isLastIndex}
          scrollBottom={scrollBottom}
          setLoading={setLoading}
        />
      </div>
      <div>
        <CopyToClipboard
          text={message}
          onCopy={() => {
            toast.success(t('copyToClipboard.success.message'));
          }}
        >
          <img className={cx('copy-btn')} src={CopyIcon} alt='copy icon' />
        </CopyToClipboard>
      </div>
    </div>
  );
};

export default LLMChatBox;
