import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

const calNoticeMessage = (value, t) => {
  if (value === 'public_api')
    return '[안내] 공공 기관 혹은 기업들이 공식적으로 제공하는 API를 활용하여 데이터를 수집합니다.';
  if (value === 'crawling')
    return '[안내] 등록한 웹 페이지의 html 파일을 수집합니다.';
  if (value === 'remote_server')
    return '[안내] 외부 서버로부터 scp 통신을 기반으로 데이터를 수집합니다.';
  return '[안내] FLIGHTBASE를 통해 배포중인 모델로 입/출력되는 데이터를 수집합니다.';
};

export default function CollectMethodRadio({ value, handleMethod }) {
  const { t } = useTranslation();

  const options = useMemo(() => {
    return [
      {
        label: 'API',
        value: 'public_api',
      },
      {
        label: t('web.crawlers'),
        value: 'crawling',
      },
      {
        label: t('remote.server'),
        value: 'remote_server',
      },
      {
        label: 'FLIGHTBASE',
        value: 'flightbase',
      },
    ];
  }, [t]);

  const noticeMessage = calNoticeMessage(value, t);

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('collect.methods.label')}
        labelSize='large'
        disableErrorMsg
      >
        <Radio
          name='collectMethod'
          value={value}
          options={options}
          onChange={handleMethod}
          isLabelColor
        />
        <p className={cx('notice')}>{noticeMessage}</p>
      </InputBoxWithLabel>
    </div>
  );
}
