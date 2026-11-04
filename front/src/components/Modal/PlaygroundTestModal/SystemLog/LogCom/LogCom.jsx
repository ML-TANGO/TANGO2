import React from 'react';

import LogAccordion from './LogAccordion';

// CSS module
import classNames from 'classnames/bind';
import style from './LogCom.module.scss';

const cx = classNames.bind(style);

export default function LogCom({ selectedItem }) {
  return (
    <div className={cx('scroll-cont')}>
      <div className={cx('log-cont')}>
        {!selectedItem && (
          <p className={cx('nodata')}>선택된 데이터가 없습니다.</p>
        )}
        {selectedItem && (
          <>
            <LogAccordion
              type='input'
              input={selectedItem.input}
              log={selectedItem.input}
            />
            {/* <LogAccordion
              type='rag'
              input={selectedItem.input}
              log={selectedItem.rag}
            />
            <LogAccordion
              type='prompt'
              input={selectedItem.input}
              log={selectedItem.prompt}
            /> */}
            <LogAccordion
              type='model'
              input={selectedItem.input}
              log={selectedItem.model}
            />
            <LogAccordion
              type='output'
              input={selectedItem.input}
              log={selectedItem.output}
            />
          </>
        )}
      </div>
      <span className={cx('start-date-txt')}>
        {selectedItem?.start_datatime}
      </span>
    </div>
  );
}
