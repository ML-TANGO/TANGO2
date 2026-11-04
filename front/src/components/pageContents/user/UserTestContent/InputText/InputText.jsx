// i18n
import { withTranslation } from 'react-i18next';

// Components
import { Textarea } from '@jonathan/ui-react';
import InputLabelBox from '../InputLabelBox';

// CSS module
import style from './InputText.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const InputText = ({
  idx,
  apiKey,
  description,
  textInputHandler,
  inputText = '',
  t,
}) => {
  return (
    <div className={cx('input-analysis')}>
      <InputLabelBox
        idx={idx}
        apiKey={apiKey}
        description={description}
        type={t('text.label')}
      />
      <div className={cx('text-box')}>
        <Textarea
          size='large'
          placeholder={t('enterText.placeholder')}
          value={inputText}
          rows={3}
          onChange={textInputHandler}
          maxLength={5000}
          isShowMaxLength
        />
      </div>
    </div>
  );
};

export default withTranslation()(InputText);
