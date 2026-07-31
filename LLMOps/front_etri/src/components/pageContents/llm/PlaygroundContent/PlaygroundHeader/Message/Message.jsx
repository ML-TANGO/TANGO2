import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';

import { calEqualValue, calIsSaveBtn } from '../PlaygroundButtonCont/util';

import classNames from 'classnames/bind';
import style from './Message.module.scss';

const cx = classNames.bind(style);

// ** [계산] 버튼 옆 메세지 출력 **
const calHeaderMessage = (
  model,
  rag,
  prompt,
  isSaveBtn,
  status,
  isFetchingStatus,
  t,
) => {
  if (isFetchingStatus)
    return {
      message: t('playground.header.connecting.message'),
      color: '#ff7A00',
    };

  const { is_rag, rag_id } = rag;
  const { is_prompt, prompt_id, prompt_system_message, prompt_user_message } =
    prompt;
  const { status: statusType } = status;

  if (['installing', 'pending'].includes(statusType))
    return {
      message: t('playground.header.setting.message'),
      color: '#FF7A00',
    };
  if (statusType === 'running')
    return {
      message: t('playground.header.running.message'),
      color: '#2D76F8',
    };
  if (!model || !model?.model_type)
    return {
      message: t('playground.header.modelLoad.message'),
      color: '#FA4E57',
    };
  if (is_rag && !rag_id)
    return {
      message: t('playground.header.ragLoad.message'),
      color: '#FA4E57',
    };
  if (is_prompt && !prompt_id && !prompt_system_message && !prompt_user_message)
    return {
      message: t('playground.header.promptLoad.message'),
      color: '#FA4E57',
    };
  if (isSaveBtn)
    return {
      message: t('playground.header.save.message'),
      color: '#FA4E57',
    };
  return { message: t('playground.header.deploy.message'), color: '#FA4E57' };
};

const Message = ({ isFetchingStatus }) => {
  const { t } = useTranslation();

  const { info, model, rag, prompt } = useSelector(
    (state) => state.llmPlayground,
    shallowEqual,
  );
  const originValue = useSelector(
    (state) => state.llmPlaygroundResetValue,
    shallowEqual,
  );
  const { status } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { status: statusType } = status;

  const isEqual = calEqualValue(info, model, rag, prompt, originValue);
  const isSaveBtn = calIsSaveBtn(
    model,
    rag,
    prompt,
    isEqual,
    statusType,
    isFetchingStatus,
  );

  // ** [데이터] 헤더 메세지 **
  const { color, message: headerMessage } = calHeaderMessage(
    model,
    rag,
    prompt,
    isSaveBtn,
    status,
    isFetchingStatus,
    t,
  );

  return (
    <p className={cx('error-message-paragraph')} style={{ color }}>
      {headerMessage}
    </p>
  );
};

export default Message;
