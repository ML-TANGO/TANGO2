import { useEffect, useRef, useState } from 'react';
import { t } from 'i18next';
import { network } from '@src/network';
import { toast } from '@src/components/Toast';
import InputLabelBox from '../InputLabelBox';
import LLMChatBox from './LLMChatBox/LLMChatBox';
import LLMMessageBox from './LLMMessageBox/LLMMessageBox';

// import RegenerateIcon from '@src/static/images/icon/ic-regenerate.svg';
import RegenerateBlackIcon from '@src/static/images/icon/ic-regenrate-black.svg';

import style from './inputLLM.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const InputLLM = ({ idx, apiKey, apiUrl, info }) => {
  const [messageArr, setMessageArr] = useState([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef();

  // * LLM Scroll이 생겼을 경우 bottom
  useEffect(() => {
    scrollBottom();
  }, [messageArr]);

  const scrollBottom = () => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  };

  // * llm 분석 API 함수
  const runAnalysisllm = async (chatArr) => {
    let header = { 'Content-Type': 'application/json;charset=UTF-8' };
    const method = info.api_method;
    const url = apiUrl.replace('http:', window.location.protocol);
    setLoading(true);
    try {
      const { data } = await network.callServiceApi({
        url,
        method,
        body: {
          llm: chatArr,
        },
        header,
      });
      setMessageArr(data.llm);
    } catch (error) {
      toast.error(`${error}`);
    }
  };

  // * 다른 결과 보기 함수
  const onClickRegenerate = () => {
    // * loading 중일 때 / messageArr이 없을 때
    if (!messageArr.length) {
      toast.error(t('llm.sendMessagePlaceholder.label'));
      return;
    }

    if (loading) {
      toast.error(t('llm.loadingError.label'));
      return;
    }

    const { input_type: inputType } = info;
    const newMessageArr = [...messageArr];

    if (inputType === 'llm-single') messageArr.pop();
    if (inputType === 'llm-multi') {
      newMessageArr.push(newMessageArr[newMessageArr.length - 2]);
      setMessageArr(newMessageArr);
    }
    runAnalysisllm(inputType === 'llm-single' ? messageArr : newMessageArr);
  };

  const messageBoxProps = {
    messageArr,
    setMessageArr,
    info,
    apiUrl,
    apiKey,
    loading,
    runAnalysisllm,
  };

  console.log('loading : ', loading);

  return (
    <div>
      <InputLabelBox idx={idx} type='LLM' apiKey={apiKey} />
      <div className={cx('llm-container')}>
        <div className={cx('llm-chat-box')} ref={scrollRef}>
          {messageArr.map((el, idx) => (
            <LLMChatBox
              key={idx}
              messageInfo={el}
              isLastIndex={messageArr.length}
              scrollBottom={scrollBottom}
              setLoading={setLoading}
            />
          ))}
        </div>
        <div className={cx('llm-bottom-box')}>
          <div
            className={cx('regenerate-btn', loading && 'unloading')}
            onClick={onClickRegenerate}
          >
            <img src={RegenerateBlackIcon} alt='regenerate-btn-img' />
            <span className={cx('regenerate-txt')}>
              {t('llm.regenerateButton.label')}
            </span>
          </div>
          <LLMMessageBox {...messageBoxProps} />
        </div>
      </div>
    </div>
  );
};

export default InputLLM;
