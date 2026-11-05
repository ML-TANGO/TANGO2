import ArrowBlackIcon from '@src/static/images/icon/00-ic-arrow-black.svg';
import React, { useEffect, useState } from 'react';

import classNames from 'classnames/bind';
import style from './LogAccordion.module.scss';

const cx = classNames.bind(style);

const Theader = {
  input: '입력',
  rag: 'RAG',
  prompt: '프롬프트',
  model: '모델',
  output: '출력',
};

export default function LogAccordion({ type, input, log }) {
  const [isOpen, setIsOpen] = useState(false);

  const title = Theader[type];

  useEffect(() => {
    setIsOpen(false);
  }, [input]);

  return (
    <div className={cx('accordion-cont')}>
      <div className={cx('header')} onClick={() => setIsOpen((prev) => !prev)}>
        <span className={cx('label')}>{title}</span>
        <img
          className={cx('arrow-img', isOpen && 'reverse')}
          src={ArrowBlackIcon}
          alt='arrow-black'
        />
      </div>
      {isOpen && (
        <div className={cx('content-cont')}>
          <div className={cx('log-cont')}>
            {log ?? '로그가 존재하지 않습니다.'}
          </div>
        </div>
      )}
    </div>
  );
}
