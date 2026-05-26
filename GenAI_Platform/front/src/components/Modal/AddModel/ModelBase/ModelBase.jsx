// Components
import { useEffect, useState } from 'react';

import Item from './Item';

// CSS Module
import classNames from 'classnames/bind';
import style from './ModelBase.module.scss';

const cx = classNames.bind(style);

function ModelBase({
  modelData,
  modelList,
  versionData,
  versionList,
  onClick,
  onSearchModel,
  onSearchVersion,
  modelSelectedItem,
  versionSelectedItem,
  onClickSubMenu,
  t,
}) {
  const [openItem, setOpenItem] = useState({ model: true, version: false });

  const handleToggle = (id) => {
    setOpenItem((prev) => ({
      model: id === 'model' ? !prev.model : false, // model 클릭 시 version 닫기
      version: id === 'version' ? !prev.version : false, // version 클릭 시 model 닫기
    }));
  };
  // id가 model일 때만 open 닫음
  const handleItemClick = (model, id) => {
    if (id === 'model') {
      // 두번째 get
      onSearchVersion({ id: model.id });
    }
    onClick(model, id);
    if (id === 'model') {
      setOpenItem((prev) => ({
        ...prev,
        model: false,
        version: true,
      }));
    }
  };

  return (
    <>
      <div className={cx('container')}>
        <Item
          id='model'
          title='모델'
          isOpen={openItem.model}
          onToggle={handleToggle}
          list={modelList}
          selectedItem={modelSelectedItem}
          onClick={(model) => handleItemClick(model, 'model')}
          data={modelData}
          onSearch={onSearchModel}
          onClickSubMenu={onClickSubMenu}
          t={t}
        />
        <div className={cx('border')} />
        <Item
          id='version'
          title='버전'
          isOpen={openItem.version}
          onToggle={handleToggle}
          list={versionList}
          selectedItem={versionSelectedItem}
          onClick={(model) => handleItemClick(model, 'version')}
          data={versionData}
          onSearch={onSearchVersion}
          onClickSubMenu={onClickSubMenu}
          t={t}
        />
      </div>
    </>
  );
}

export default ModelBase;
