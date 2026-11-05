import { Button } from '@jonathan/ui-react';

import MenuIcon from '@src/static/images/icon/00-ic-menu.svg';
import React from 'react';

import DropMenu from '@src/components/molecules/DropMenu';
import BtnMenu from '@src/components/molecules/DropMenu/BtnMenu';

import classNames from 'classnames/bind';
import style from './ToolCardHeader.module.scss';

const cx = classNames.bind(style);

const ToolCardHeader = ({
  toolType,
  toolName,
  toolReplicaNum,
  menuBtnList,
}) => {
  return (
    <div className={cx('header')}>
      <div className={cx('left-box')}>
        <div className={cx('icon')}>
          {toolType === 'default' ? (
            toolName && (
              <div className={cx('initial')}>
                {toolName.slice(0, 1).toUpperCase()}
              </div>
            )
          ) : (
            <img
              src={`/images/icon/ic-${toolType}.svg`}
              alt={`${toolType} icon`}
            />
          )}
        </div>
        {toolReplicaNum > 0 && (
          <div className={cx('tool-replica-number')}>
            {toolReplicaNum < 10 ? `0${toolReplicaNum}` : toolReplicaNum}
          </div>
        )}
      </div>
      <div className={`${cx('popup-wrap')} event-block`}>
        <DropMenu
          btnRender={() => (
            <Button
              type='none-border'
              size='small'
              iconAlign='left'
              icon={MenuIcon}
              iconStyle={{ margin: '0', width: '24px', height: '24px' }}
              customStyle={{ width: '30px', padding: '6px' }}
            />
          )}
          menuRender={(popupHandler) => (
            <BtnMenu btnList={menuBtnList} callback={popupHandler} />
          )}
          align='RIGHT'
        />
      </div>
    </div>
  );
};

export default ToolCardHeader;
