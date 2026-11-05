// i18n
import { useTranslation } from 'react-i18next';

import { getKoreaTime } from '@src/datetimeUtils';

// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingAuth.module.scss';

const cx = classNames.bind(style);

function TrainingAuth({ accessInfo, basicInfo, instanceInfo }) {
  const { t } = useTranslation();
  const { access, owner, userList } = accessInfo;
  const { name, description, createDatetime, createName } = basicInfo;
  const {
    instanceCount,
    instanceName,
    gpu,
    gpuName,
    cpu,
    ram,
    type,
    huggingfaceId,
    category,
    builtInModel,
  } = instanceInfo;

  return (
    <div className={cx('training-auth')}>
      <div className={cx('training')}>
        <div className={cx('header')}>
          <span className={cx('title')}>
            {t('basicInformationSettings.title.label')}
          </span>
          <div className={cx('btn-wrap')}></div>
        </div>
        <div className={cx('content')}>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('projectName.label')}</div>
            <div className={cx('value')}>{name}</div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('projectDescription.label')}</div>
            <div className={cx('value')}>{description}</div>
          </div>
          <div className={cx('item', 'model-type')}>
            <div className={cx('label')}>{t('modelType.label')}</div>
            <div className={cx('value', 'type-value')}>
              {type === 'advanced' && 'Custom'}
              {type === 'huggingface' && (
                <>
                  <span className={cx('model-type-value')}>
                    <img
                      src={'/images/icon/ic-training-black.svg'}
                      alt='model-icon'
                    />
                    {category}
                  </span>
                  <span className={cx('model-type-value')}>
                    <img
                      src={'/src/static/images/icon/hugging-face.svg'}
                      alt='model-icon'
                    />

                    {huggingfaceId}
                  </span>
                </>
              )}
              {type === 'built-in' && (
                <>
                  <span className={cx('model-type-value')}>
                    <img src={'/images/icon/ic-medical.svg'} alt='model-icon' />
                    {category}
                  </span>
                  <span className={cx('model-type-value')}>
                    <img
                      src={'/images/icon/ic-jonathanIntelligence.svg'}
                      alt='model-icon'
                    />
                    {builtInModel}
                  </span>
                </>
              )}
            </div>
          </div>

          <div className={cx('item')}>
            <div className={cx('label')}>{t('createdDatetime.label')}</div>
            <div className={cx('value')}>{getKoreaTime(createDatetime)}</div>
          </div>
        </div>
      </div>
      {/* 인스턴스 */}
      <div className={cx('training')}>
        <div className={cx('header')}>
          <span className={cx('title')}>{t('instanceSetting.label')}</span>
          <div className={cx('btn-wrap')}></div>
        </div>
        <div className={cx('content')}>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('instanceName.label')}</div>
            <div className={cx('value')}>{instanceName}</div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('instanceCount.label')}</div>
            <div className={cx('value')}>{instanceCount}</div>
          </div>
        </div>
        <div className={cx('header')}>
          <span className={cx('title')}>
            {t('instanceConfiguration.label')}
          </span>
        </div>
        <div className={cx('content')}>
          <div className={cx('item')}>
            <div className={cx('label')}>vGPU</div>
            <div className={cx('value')}>
              {gpuName && gpu ? `${gpuName} x ${gpu}EA` : '-'}
            </div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>vCPU</div>
            <div className={cx('value')}>{cpu ? `${cpu} Cores` : '-'}</div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>RAM</div>
            <div className={cx('value')}>{ram ? `${ram} GB` : '-'}</div>
          </div>
        </div>
      </div>

      {/* 접근 권한 설정 */}
      <div className={cx('training')}>
        <div className={cx('header')}>
          <span className={cx('title')}>{t('accessSettings.title.label')}</span>
          <div className={cx('btn-wrap')}></div>
        </div>
        <div className={cx('content')}>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('accessType.label')}</div>
            <div className={cx('value')}>
              {access === 1 ? 'public' : 'private'}
            </div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('owner.label')}</div>
            <div className={cx('value')}>{createName}</div>
          </div>
          <div className={cx('item')}>
            <div className={cx('label')}>{t('user.label')}</div>
            <div className={cx('value')}>
              {userList && userList.length > 0
                ? userList.map((u) => u.user_name).join(', ')
                : '-'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TrainingAuth;
