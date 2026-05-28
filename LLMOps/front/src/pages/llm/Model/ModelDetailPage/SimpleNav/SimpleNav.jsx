// Components
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { NavLink } from 'react-router-dom';

import { Checkbox } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './SimpleNav.module.scss';

const cx = classNames.bind(style);

function SimpleNav({ navList, topButtonList, titleName, subTitle, checkbox }) {
  const { t } = useTranslation();
  const { info } = useSelector((state) => state.llmModel, shallowEqual);
  if (!navList) {
    console.warn('No navList');
    return null;
  }

  return (
    <div className={cx('nav-box')}>
      <div className={cx('title')}>
        <div className={cx('name')}>
          <div>{info?.name ?? titleName}</div>
          {subTitle && <div className={cx('sub-title')}>{subTitle}</div>}
        </div>
        {topButtonList && <div className={cx('btn')}>{topButtonList}</div>}
      </div>
      <ul className={cx('nav')}>
        {navList.map(({ label, path }, idx) => (
          <li className={cx('nav-item')} key={idx}>
            <NavLink exact to={path} activeClassName={cx('active')}>
              <span className={cx('link-name')}>{t(label)}</span>
              <span className={cx('stick')}></span>
            </NavLink>
          </li>
        ))}
        {/* {checkbox && (
          <li className={cx('checkbox', checkbox.disabled && 'disabled')}>
            <div className={cx('checkbox-wrap')}>
              <Checkbox
                checked={checkbox.checked}
                onChange={checkbox.handler}
                disabled={checkbox.disabled}
                customStyle={{
                  backgroundColor: checkbox.checked ? '#3BABFF' : 'transparent',
                  borderColor: '#3BABFF',
                  paddingRight: '0px',
                }}
              />
              <span>{t('finetuning.accelator')}</span>
            </div>
          </li>
        )} */}
      </ul>
    </div>
  );
}

export default SimpleNav;
