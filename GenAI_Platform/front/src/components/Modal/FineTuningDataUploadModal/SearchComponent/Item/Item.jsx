// Components
import { Badge, Button, InputText } from '@jonathan/ui-react';

import SubMenuItem from './SubMenuItem';

// CSS Module
import classNames from 'classnames/bind';
import style from './Item.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';

const cx = classNames.bind(style);
const defaultMenuOption = [
  { label: 'total.label', value: 'total' },
  { label: 'me.label', value: 'me' },
];

function Item({
  id,
  title,
  isOpen,
  onToggle,
  list,
  selectedItem,
  onClick,
  data,
  onSearch,
  onClickSubMenu,
  icon,
  tabMenuTitle = 'releaseType.label',
  noSelectedDataMessage,
  menuOptions,
  t,
}) {
  return (
    <>
      <div className={cx('bar')} onClick={() => onToggle(id)}>
        <div className={cx('title-box')}>
          <div className={cx('title')}>{t(title)}</div>
          <div
            className={cx('content', selectedItem?.name && 'selected-content')}
          >
            <div className={cx('name')}>
              {selectedItem?.name || t(noSelectedDataMessage)}
            </div>
          </div>
        </div>
        <div className={cx('arrow-train')}>
          <img src={isOpen ? arrowUp : arrowDown} alt='arrow' />
        </div>
      </div>
      {isOpen && (
        <>
          <div className={cx('search-content')}>
            <div className={cx('input')}>
              <InputText
                value={data.keyword}
                onChange={(e) => onSearch({ keyword: e.target.value })}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                customStyle={{ height: '32px' }}
              />
            </div>
            <div className={cx('button-box')}>
              <div className={cx('button')}>
                <span className={cx('type-title')}>{t(tabMenuTitle)}</span>
                <SubMenuItem
                  option={menuOptions ?? defaultMenuOption}
                  select={data.selectedOption}
                  onChangeHandler={(e) => onClickSubMenu(e, id)}
                  customStyle={{
                    marginBottom: 0,
                    marginRight: 0,
                  }}
                  labelHeight={{}}
                  size={'xsmall'}
                />
              </div>
            </div>
          </div>
          <div className={cx('list-content')}>
            {list?.map((model, i) => {
              const { name, create_user_name: user } = model;
              return (
                <div
                  className={cx(
                    'list',
                    name === selectedItem?.name && 'selected',
                  )}
                  onClick={() => onClick(model)}
                  key={i}
                >
                  <div className={cx('left')}>
                    {icon && <img src={icon} alt='icon' />}
                    <div className={cx('name')}>
                      {name}
                      {name === selectedItem?.name && (
                        <img
                          src={
                            '/src/static/images/icon/00-ic-deploy-selected-file.svg'
                          }
                          alt='icon'
                        />
                      )}
                    </div>
                  </div>
                  <div className={cx('user')}>{user}</div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}

export default Item;
