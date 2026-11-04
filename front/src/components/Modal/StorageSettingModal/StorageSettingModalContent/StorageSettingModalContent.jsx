// Components
import { Button, InputText, Tooltip } from '@jonathan/ui-react';

// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './StorageSettingModalContent.module.scss';
const cx = classNames.bind(style);

function StorageSettingModalContent(props) {
  const {
    newCreateHandler,
    distributionBtnHandler,
    distributionBtn,
    inputValueHandler,
    inputValue,
    newCreateBtn,
    nameError,
    workspaces, // 해당 스토리지의 워크스페이스 수
    storageName,
  } = props?.data;
  const { t } = useTranslation();

  return (
    <div className={cx('container')}>
      <div className={cx('label')}>{t('storageName.label')}</div>
      <InputText
        name='name'
        placeholder={t('storageName.placeholder')}
        value={inputValue}
        disableClearBtn={false}
        disabelLeftIcon={true}
        onChange={(e) => {
          inputValueHandler(e.target.value);
        }}
        status={nameError ? 'error' : 'default'}
        isReadOnly={storageName === 'MAIN_STORAGE'}
      />
      <div className={cx('error')}>{t(nameError)}</div>
      <div className={cx('label')}>
        {t('storageDistributionType.label')}
        <div
          className={cx(
            'distribution-method-box',
            storageName === 'MAIN_STORAGE' || workspaces ? 'disabled-box' : '',
          )}
        >
          <div
            className={cx(
              'allocate',
              distributionBtn.allocate && 'check',

              workspaces && !distributionBtn.allocate ? 'disabled' : '',
              !workspaces &&
                storageName === 'MAIN_STORAGE' &&
                !distributionBtn.allocate
                ? 'main-disabled'
                : '',
            )}
            onClick={() => {
              distributionBtnHandler('allocate');
            }}
          >
            <div className={cx('allocate-label')}>{t('allocate.label')}</div>
            <div className={cx('image-box')}>
              <div className={cx('image')}>
                <img
                  src='/images/icon/00-ic-storage-allocate.png'
                  alt='guarantee_image'
                />
              </div>
              <div className={cx('bottom-message')}>
                {t('storageAllocate.messsage')}
              </div>
            </div>
            {storageName !== 'MAIN_STORAGE' && !workspaces ? (
              <div className={cx('btn')}>{t('select.label')}</div>
            ) : (
              ''
            )}
          </div>

          <div
            className={cx(
              'share',
              distributionBtn.share && 'check',

              workspaces && !distributionBtn.share ? 'disabled' : '',
              !workspaces &&
                storageName === 'MAIN_STORAGE' &&
                !distributionBtn.share
                ? 'main-disabled'
                : '',
            )}
            onClick={() => {
              distributionBtnHandler('share');
            }}
          >
            <div className={cx('share-label')}>{t('share.label')}</div>
            <div className={cx('image-box')}>
              <div className={cx('image')}>
                <img
                  src='/images/icon/00-ic-storage-share.png'
                  alt='guarantee_image'
                />
              </div>
              <div className={cx('bottom-message')}>
                {t('storageShare.message')}
              </div>
            </div>
            {storageName !== 'MAIN_STORAGE' && !workspaces ? (
              <div className={cx('btn')}>{t('select.label')}</div>
            ) : (
              ''
            )}
          </div>
        </div>
      </div>
      <div className={cx('label')}>
        {t('WorkspaceGeneration.label')}
        <Tooltip
          contents={t('storageWorkspaceGeneration.tooltip.message')}
          contentsAlign={{ vertical: 'top', horizontal: 'left' }}
        >
          <img
            className={cx('tooltip-icon')}
            src='/images/icon/00-ic-alert-error-b.svg'
            alt='informantion'
          />
        </Tooltip>
        <div className={cx('new-create-box')}>
          <div>
            <Button
              onClick={() => newCreateHandler('allowed')}
              customStyle={{
                width: '80px',
                borderRadius: '0px',
                color: !newCreateBtn.allowed && '#C1C1C1',
                backgroundColor: !newCreateBtn.allowed && '#ffffff',
                borderColor: !newCreateBtn.allowed && '#C1C1C1',
              }}
            >
              {t('allowed.label')}
            </Button>
          </div>
          <div>
            <Button
              onClick={() => {
                newCreateHandler('limited');
              }}
              customStyle={{
                borderRadius: '0px',
                width: '80px',
                color: !newCreateBtn.limited && '#C1C1C1',
                backgroundColor: !newCreateBtn.limited ? '#ffffff' : '#FA4E57',
                borderColor: !newCreateBtn.limited ? '#C1C1C1' : '#FA4E57',
              }}
            >
              {t('limited.label')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default StorageSettingModalContent;
