// Components
import { useState } from 'react';

import Item from './Item';

// CSS Module
import classNames from 'classnames/bind';
import style from './DatasetUploadSearchCom.module.scss';

const cx = classNames.bind(style);

function DatasetUploadSearchCom({
  firstData,
  firstList,
  secondData, // optional
  secondList, // optional
  firstIcon,
  secondIcon,
  onClick,
  tabMenuTitle,
  onSearchFirst,
  onSearchSecond, // optional
  firstSelectedItem,
  secondSelectedItem, // optional
  onClickSubMenu,
  noSelectedDataMessage,
  menuOptions,
  title,
  t,
}) {
  const [openItem, setOpenItem] = useState({ first: false, second: false });

  const handleToggle = (id) => {
    setOpenItem((prev) => ({
      first: id === 'first' ? !prev.first : false,
      second: id === 'second' ? !prev.second : false,
    }));
  };

  // id가 first 때만 open 닫음
  const handleItemClick = (model, id) => {
    if (id === 'first' && onSearchSecond) {
      onSearchSecond({ id: model.id });
      setOpenItem((prev) => ({
        ...prev,
        first: false,
        second: true,
      }));
    }
    onClick(model, id); // 얘만 항상 실행
  };

  return (
    <>
      <div className={cx('container')}>
        <Item
          id='first'
          title={title.first}
          isOpen={openItem.first}
          onToggle={handleToggle}
          list={firstList}
          selectedItem={firstSelectedItem}
          onClick={(model) => handleItemClick(model, 'first')}
          data={firstData}
          onSearch={onSearchFirst}
          onClickSubMenu={onClickSubMenu}
          tabMenuTitle={tabMenuTitle}
          noSelectedDataMessage={noSelectedDataMessage.first}
          icon={firstIcon}
          menuOptions={menuOptions}
          t={t}
        />
        {secondData && secondList && (
          <>
            <div className={cx('border')} />
            <Item
              id='second'
              title={title.second}
              isOpen={openItem.second}
              onToggle={handleToggle}
              list={secondList}
              selectedItem={secondSelectedItem}
              onClick={(model) => handleItemClick(model, 'second')}
              data={secondData}
              tabMenuTitle={tabMenuTitle}
              onSearch={onSearchSecond}
              onClickSubMenu={onClickSubMenu}
              noSelectedDataMessage={noSelectedDataMessage.second}
              icon={secondIcon}
              menuOptions={menuOptions}
              t={t}
            />
          </>
        )}
      </div>
    </>
  );
}

export default DatasetUploadSearchCom;
