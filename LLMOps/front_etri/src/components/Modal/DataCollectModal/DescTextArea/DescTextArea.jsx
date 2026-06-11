import { useTranslation } from 'react-i18next';

import { Textarea } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export default function DescTextArea({ value, handleDescribe }) {
  const { t } = useTranslation();
  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('collect.desc.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
      >
        <Textarea
          name='desc'
          size='large'
          placeholder={t('collect.desc.placeholder')}
          value={value}
          onChange={handleDescribe}
          customStyle={{ fontSize: '14px', height: '80px' }}
          isShowMaxLength
        />
      </InputBoxWithLabel>
    </div>
  );
}
