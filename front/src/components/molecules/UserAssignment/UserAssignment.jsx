import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

import ButtonList from './ButtonList';
import UserSelect from './UserSelect';

import classNames from 'classnames/bind';
import style from './UserAssignment.module.scss';

const cx = classNames.bind(style);

export default function UserAssignment({
  title = '사용자 입력',
  firstLabel = '사용자 선택',
  secondLabel = '선택된 사용자',
  placeholder = '사용자 검색',
  list = [],
  selectedList = [],
}) {
  const { t } = useTranslation();

  const [pickedList, setPickedList] = useState(new Map());

  const handlePickUser = useCallback(
    (user) => {
      const newPickedUser = new Map(pickedList);
      const getIsPickValue = newPickedUser.get(user.id);

      if (getIsPickValue) {
        newPickedUser.delete(user.id);
      } else {
        newPickedUser.set(user.id, user);
      }

      setPickedList(newPickedUser);
    },
    [pickedList],
  );

  return (
    <div className={cx('user-assign-cont')}>
      <label htmlFor='user-select' className={cx('label')}>
        {title}
        <small>{t('optional.label')}</small>
      </label>
      <div className={cx('select-cont')}>
        <UserSelect
          type='unselected'
          label={firstLabel}
          placeholder={placeholder}
          list={list}
          pickedList={pickedList}
          handlePickUser={handlePickUser}
        />
        <ButtonList />
        <UserSelect
          type='selected'
          label={secondLabel}
          placeholder={placeholder}
          list={selectedList}
          pickedList={pickedList}
          handlePickUser={handlePickUser}
        />
      </div>
    </div>
  );
}
