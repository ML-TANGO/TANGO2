// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';
import DropMenu from '@src/components/molecules/DropMenu';

// CSS Module
import classNames from 'classnames/bind';
import style from './Resource.module.scss';

const cx = classNames.bind(style);

function Resource({ resourceInfo }) {
  const { t } = useTranslation();
  const {
    configurations,
    resource_usage: { cpu, gpu },
  } = resourceInfo;
  const isActive = configurations.length > 0;

  return (
    <div className={`${cx('resource', !isActive && 'disabled')} event-block`}>
      <DropMenu
        maxHeight={'230px'}
        menuRender={() => (
          <div className={cx('item-box')}>
            <div className={cx('label-count')}>
              <span>GPU * {gpu}</span>
              <span>|</span>
              <span>CPU * {cpu}</span>
            </div>
            <ul className={cx('config-list')}>
              {configurations.map((name, idx) => (
                <li key={idx}>{name}</li>
              ))}
            </ul>
          </div>
        )}
        btnRender={(isUp) => (
          <Button
            type='primary-light'
            icon={'/images/icon/ic-resource-blue.svg'}
            disabled={!isActive}
            customStyle={{
              backgroundColor: isUp
                ? '#c8dbfd'
                : isActive
                ? '#dee9ff'
                : '#f9fafb',
              borderColor: isUp ? '#c8dbfd' : isActive ? '#dee9ff' : '#f9fafb',
            }}
          >
            {t('resource.label')}
          </Button>
        )}
        align='RIGHT'
        isDropUp={false}
      />
    </div>
  );
}

export default Resource;
