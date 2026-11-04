import { Radio } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

const InstanceTypeInput = ({
  idx,
  selectedValue,
  onChangeValue,
  radioOptions,
}) => {
  return (
    <InputBoxWithLabel disableErrorMsg>
      <Radio
        name={`instanceType-${idx}`}
        selectedValue={selectedValue}
        options={radioOptions}
        customStyle={{
          marginBottom: '32px',
          transform: 'translateX(-6px)',
        }}
        onChange={(e) => onChangeValue(e)}
        isReadonly
      />
    </InputBoxWithLabel>
  );
};

export default InstanceTypeInput;
