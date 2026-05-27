import { Button } from '@jonathan/ui-react';

import { t } from 'i18next';
import { useRef, useState } from 'react';

import { toast } from '@src/components/Toast';

import classNames from 'classnames/bind';
import style from './LLMMessageBox.module.scss';

const cx = classNames.bind(style);

const LLMMessageBox = ({
  messageArr,
  setMessageArr,
  info,
  loading,
  runAnalysisllm,
}) => {
  const [message, setMessage] = useState('');
  const inputRef = useRef();
  const { input_type: inputType, data_input_form_list: inputFormList } = info;

  // * 분석 시작 버튼
  const onClickAnalysis = () => {
    if (!message) {
      toast.error(t('llm.sendMessagePlaceholder.label'));
      return;
    }

    // * llm-single / llm-multi 조건
    const chatArr = inputType === 'llm-single' ? [] : [...messageArr];
    chatArr.push({
      type: 'input',
      message,
    });
    setMessageArr(chatArr);

    // * 분석 시작 버튼 클릭 후 message 초기화 및 focus
    setMessage('');
    inputRef.current.focus();

    runAnalysisllm(chatArr);
  };

  return (
    <div className={cx('input-box')}>
      <input
        className={cx('generate-input')}
        type='text'
        placeholder={t('llm.sendMessagePlaceholder.label')}
        onChange={(e) => setMessage(e.target.value)}
        value={message}
        ref={inputRef}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onClickAnalysis();
          }
        }}
      />
      <Button
        customStyle={{ height: '40px' }}
        type='primary'
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onClickAnalysis();
        }}
        loading={inputFormList && loading}
      >
        {t('startAnalysis.label')}
      </Button>
    </div>
  );
};

export default LLMMessageBox;
