// i18n

// Components
import { InputText, Tooltip } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import CheckboxList from '@src/components/molecules/CheckboxList';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './DeploymentOutputTypeBox.module.scss';

const cx = classNames.bind(style);

function DeploymentOutputTypeBox({
  deploymentOutputTypes,
  otherDeploymentOutputTypes,
  otherDeploymentOutputTypesError,
  deploymentOutputTypesHandler,
  textInputHandler,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('wrapper')}>
      <div className={cx('row')}>
        <CheckboxList
          label='deploymentOutputTypes.label'
          options={deploymentOutputTypes}
          onChange={(_, idx) => deploymentOutputTypesHandler(idx)}
          customStyle={{
            display: 'flex',
            flexDirection: 'column',
          }}
          labelRight={
            <Tooltip
              contents={t('deploymentOutputTypes.tooltip.message')}
              contentsCustomStyle={{
                fontFamily: 'SpoqaM',
              }}
            />
          }
          disableErrorText
        />
      </div>
      <div className={cx('row', 'etc')}>
        <InputBoxWithLabel errorMsg={t(otherDeploymentOutputTypesError)}>
          <InputText
            size='medium'
            placeholder={t('enterOther.placeholder')}
            name='otherDeploymentOutputTypes'
            value={otherDeploymentOutputTypes}
            onChange={textInputHandler}
            isDisabled={
              !deploymentOutputTypes[deploymentOutputTypes.length - 1].checked
            }
            disableLeftIcon
            disableClearBtn
            customStyle={{
              padding: '11px 12px',
              border: '1px solid #dbdbdb',
              borderRadius: '2px',
              backgroundColor: '#fff',
              fontSize: '14px',
              fontWeight: '500',
              lineHeight: '14px',
            }}
          />
        </InputBoxWithLabel>
      </div>
    </div>
  );
}

export default DeploymentOutputTypeBox;
