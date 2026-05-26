import { InputText } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

const InstanceNameInput = ({
  t,
  idx,
  value,
  isReadOnly,
  disableLeftIcon,
  disableClearBtn,
}) => {
  return (
    <InputBoxWithLabel
      labelText={`${t('instance.label')}#${idx} ${t('name.label')}`}
      labelSize='large'
      disableErrorMsg
      style={{ marginBottom: '32px' }}
    >
      <InputText
        size='medium'
        onChange={() => {
          console.log('inputHandler');
        }}
        name='instance name'
        value={value}
        isReadOnly={isReadOnly}
        disableLeftIcon={disableLeftIcon}
        disableClearBtn={disableClearBtn}
      />
    </InputBoxWithLabel>
  );
};

export default InstanceNameInput;
