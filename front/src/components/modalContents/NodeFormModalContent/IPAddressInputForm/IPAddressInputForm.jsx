// i18n
import { useTranslation } from 'react-i18next';

// Molecules
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Atoms
import TextInput from '@src/components/atoms/input/TextInput';
import Button from '@src/components/atoms/button/Button';

// CSS Module
import classNames from 'classnames/bind';
import style from './IPAddressInputForm.module.scss';
const cx = classNames.bind(style);

/**
 * 노드 생성 수정 폼에서 사용되는 IP주소 입력 폼 컴포넌트
 * @param {{ ipAddress: string, inputHandler: Function, getNetworkInfo: Function, ipAddressError: string, type: 'ADD_NODE' | 'EDIT_NODE' | 'ADD_STORAGE_NODE' | 'EDIT_STORAGE_NODE' }} props
 * @returns
 */
function IPAddressInputForm({
  ipAddress,
  inputHandler,
  ipAddressError,
  getNetworkInfo,
  type,
}) {
  const { t } = useTranslation();
  const isEdit = type.indexOf('EDIT') !== -1;

  return (
    <InputBoxWithLabel
      labelText={t('ipAddress.label')}
      labelSize='large'
      errorMsg={t(ipAddressError)}
    >
      {isEdit ? (
        <TextInput
          value={ipAddress}
          name='ipAddress'
          onChange={inputHandler}
          placeholder='IP Address'
          status={
            ipAddressError === '' || !ipAddressError ? 'success' : 'error'
          }
          readOnly={isEdit}
        />
      ) : (
        <div className={cx('ip-input-wrap')}>
          <TextInput
            value={ipAddress}
            name='ipAddress'
            onChange={inputHandler}
            placeholder='IP Address'
            status={
              ipAddressError === '' || !ipAddressError ? 'success' : 'error'
            }
            readOnly={isEdit}
            autoFocus={true}
          />
          <Button
            onClick={getNetworkInfo}
            type='secondary'
            disabled={!(ipAddressError === '')}
          >
            {t('getInfo.label')}
          </Button>
        </div>
      )}
    </InputBoxWithLabel>
  );
}

export default IPAddressInputForm;
