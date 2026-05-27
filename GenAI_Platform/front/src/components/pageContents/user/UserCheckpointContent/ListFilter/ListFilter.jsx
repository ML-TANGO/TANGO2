import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Button from '@src/components/atoms/button/Button';
import TextInput from '@src/components/atoms/input/TextInput';

import { openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './ListFilter.module.scss';

const cx = classNames.bind(style);

let timer;

function ListFilter({ refreshData }) {
  // 다국어
  const { t } = useTranslation();

  // Redux Hooks
  const dispatch = useDispatch();

  // Component State
  const [search, setSearch] = useState(''); // 검색 창 입력 값

  // eslint-disable-next-line no-unused-vars
  const [searchText, setSearchText] = useState(''); // 실제 목록 필터링을 위한 마지막에 최종 입력한 텍스트 값

  // Event
  const inputHandler = (e) => {
    const { value } = e.target;
    if (timer) {
      clearTimeout(timer);
    }

    timer = setTimeout(() => {
      setSearchText(value);
    }, 500);

    setSearch(value);
  };

  const openUploadCkpModal = () => {
    dispatch(
      openModal({
        modalType: 'UPLOAD_CHECKPOINT',
        modalData: {
          submit: {
            text: t('upload.label'),
            func: () => {
              refreshData();
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
        },
      }),
    );
  };

  return (
    <div className={cx('list-filter')}>
      <div className={cx('filter-wrap')}>
        <div className={cx('left-box')}>
          <Button type='primary' onClick={openUploadCkpModal}>
            {t('uploadCheckpoint.label')}
          </Button>
        </div>
        <div className={cx('right-box')}>
          {/* Search */}
          <TextInput
            value={search}
            onChange={inputHandler}
            leftIconPath='/images/icon/ic-search.svg'
            placeholder={t('search.placeholder')}
          />
        </div>
      </div>
    </div>
  );
}
export default ListFilter;
