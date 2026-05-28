// Components
import { InputText } from '@jonathan/ui-react';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import { useState } from 'react';

import SubMenu from '@src/components/molecules/SubMenu';

import NewStyleModalFrame from '../../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './SearchTable.module.scss';

const cx = classNames.bind(style);

function SearchTable() {
  const [selectedItem, setSelectedItem] = useState({});
  const [openItem, setOpenItem] = useState({});

  const handleToggle = (index) => {
    setOpenItem((prevState) => {
      // 모든 값을 false로 초기화한 뒤, 클릭한 index의 값만 true로 설정
      const newState = Object.keys(prevState).reduce((acc, key) => {
        acc[key] = false;
        return acc;
      }, {});

      // 클릭한 index의 값을 현재와 반대로 설정
      newState[index] = !prevState[index];

      return newState;
    });
  };

  const ownerMenuOptions = [
    { label: 'all.label', value: 'allOwner' },
    { label: 'owner', value: 'owner' },
  ];

  const [trainingSelectedOwner, setTrainingSelectedOwner] = useState({
    label: 'all.label',
    value: 'allOwner',
  });

  return (
    <>
      <div className={cx('container')}>
        {test.map(({ title, noSelectedMessage, btn, items }, idx) => {
          return (
            <>
              <div className={cx('bar')} onClick={() => handleToggle(idx)}>
                <div className={cx('title-box')}>
                  <div className={cx('title')}>{title}</div>
                  <div
                    className={cx(
                      'content',
                      selectedItem[idx] && 'selected-content',
                    )}
                  >
                    {selectedItem[idx] ? selectedItem[idx] : noSelectedMessage}
                  </div>
                </div>
                <div className={cx('arrow-train')}>
                  <img src={openItem[idx] ? arrowUp : arrowDown} alt='arrow' />
                </div>
              </div>
              {openItem[idx] && (
                <div className={cx('search-content')}>
                  <div className={cx('input')}>
                    <InputText
                      value={selectedItem[idx]}
                      onChange={(e) => console.log(e)}
                      disableLeftIcon={false}
                      placeholder={'이름, 설명'}
                    />
                  </div>
                  <div className={cx('button-box')}>
                    <div className={cx('button')}>
                      <span className={cx('type-title')}>{btn?.btnTitle}</span>
                      <SubMenu
                        option={ownerMenuOptions}
                        select={trainingSelectedOwner}
                        onChangeHandler={(e) => {
                          console.log(e);
                        }}
                        customStyle={{ marginBottom: 0, marginRight: 0 }}
                        size={'small'}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          );
        })}
      </div>
    </>
  );
}

export default SearchTable;
