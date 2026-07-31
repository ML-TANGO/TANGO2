// Components
import { Badge, Button, InputText } from '@tango/ui-react';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';

import SubMenu from '@src/components/molecules/SubMenu';

// CSS Module
import classNames from 'classnames/bind';
import style from './Item.module.scss';

const cx = classNames.bind(style);
const menuOptions = [
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
  t,
}) {
  return (
    <>
      <div className={cx('bar')} onClick={() => onToggle(id)}>
        <div className={cx('title-box')}>
          <div className={cx('title')}>{title}</div>
          <div
            className={cx('content', selectedItem?.name && 'selected-content')}
          >
            <div className={cx('name')}>
              {selectedItem?.name ||
                (id === 'model'
                  ? t('modelSelect.message')
                  : t('versionSelect.message'))}
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
                placeholder={'이름'}
              />
            </div>
            <div className={cx('button-box')}>
              <div className={cx('button')}>
                <span className={cx('type-title')}>공개 범위</span>
                <SubMenu
                  option={menuOptions}
                  select={data.selectedOption}
                  onChangeHandler={(e) => onClickSubMenu(e, id)}
                  customStyle={{ marginBottom: 0, marginRight: 0 }}
                  size={'small'}
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
                    <div className={cx('name')}>{name}</div>
                    {name === selectedItem?.name && (
                      <div className={cx('name-icon')}></div>
                    )}
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
