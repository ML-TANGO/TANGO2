// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './ApiInputForm.module.scss';
const cx = classNames.bind(style);

function ApiInputForm({
  apiAddress,
  endpoint,
  endpointError,
  textInputHandler,
}) {
  const { t } = useTranslation();
  const apiHost = apiAddress.includes('/deployment/')
    ? `${apiAddress.split('/deployment/')[0]}/deployment/`
    : `${apiAddress.split(':server_port/')[0]}:server_port/`;

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('apiAddress.label')}
        errorMsg={t(endpointError)}
      >
        <InputBoxWithLabel labelText={apiHost} leftLabel bgBox>
          <InputText
            placeholder='endpoint'
            value={endpoint}
            name='endpoint'
            onChange={textInputHandler}
            status={endpointError ? 'error' : 'default'}
            options={{ maxLength: 100 }}
            disableLeftIcon={true}
            disableClearBtn={false}
            onClear={() => {
              textInputHandler({
                target: { value: '', name: 'endpoint' },
              });
            }}
          />
          <span className={cx('slash')}>/</span>
        </InputBoxWithLabel>
      </InputBoxWithLabel>
    </div>
  );
}

export default ApiInputForm;
