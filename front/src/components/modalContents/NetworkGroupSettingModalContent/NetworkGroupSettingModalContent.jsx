// i18n
import { useTranslation } from 'react-i18next';

// Components
import ModalFrame from '@src/components/Modal/ModalFrame';
// import Loading from '@src/components/atoms/loading/Loading';
import Tab from '@src/components/molecules/Tab';

// CSS module
import classNames from 'classnames/bind';
import style from './NetworkGroupSettingModalContent.module.scss';
const cx = classNames.bind(style);

function NetworkGroupSettingModalContent({
  type,
  modalData,
  targetOptions,
  target,
  setTarget,
  isLoading,
  renderBasicInfoForm,
  onBasicInfoUpdate,
  renderNodeInterfaceForm,
  onNodeInterfaceUpdate,
  renderContainerInterfaceForm,
  onContainerInterfaceUpdate,
  renderIpRangeForm,
  onIpRangeUpdate,
  isValidate,
}) {
  const { t } = useTranslation();
  const isSetting = type === 'NETWORK_GROUP_SETTING';

  const { submit, cancel } = modalData;
  const newSubmit = {
    text: submit.text, // 탭별 버튼 텍스트 수정
    func: async () => {
      if (!isSetting) {
        const res = await onBasicInfoUpdate(submit.func);
        return res;
      } else {
        // 각 탭별 정보 업데이트
        if (target.value === 'basic') {
          const res = await onBasicInfoUpdate(submit.func);
          return res;
        } else if (target.value === 'node') {
          const res = await onNodeInterfaceUpdate(submit.func);
          return res;
        } else if (target.value === 'container') {
          const res = await onContainerInterfaceUpdate(submit.func);
          return res;
        } else if (target.value === 'ip') {
          const res = await onIpRangeUpdate(submit.func);
          return res;
        }
      }
    },
  };

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={isValidate}
      isResize={true}
      isMinimize={true}
      title={
        isSetting
          ? t('network.setting.group.label')
          : t('network.create.group.label')
      }
    >
      <h2 className={cx('title')}>
        {isSetting
          ? t('network.setting.group.label')
          : t('network.create.group.label')}
      </h2>
      <div className={cx('tab-box')}>
        {isSetting && (
          <Tab
            type='a'
            option={targetOptions}
            select={target}
            tabHandler={setTarget}
            backgroudColor='#fff'
          />
        )}
      </div>
      <div className={cx('modal-content')}>
        <div className={cx('tab-title')}>
          {target.label} {t('network.settings.label')}
        </div>
        <div className={cx('tab-content')}>
          {target.value === 'basic' && renderBasicInfoForm()}
          {target.value === 'node' && renderNodeInterfaceForm()}
          {target.value === 'container' && renderContainerInterfaceForm()}
          {target.value === 'ip' && renderIpRangeForm()}
        </div>
      </div>
    </ModalFrame>
  );
}

export default NetworkGroupSettingModalContent;
