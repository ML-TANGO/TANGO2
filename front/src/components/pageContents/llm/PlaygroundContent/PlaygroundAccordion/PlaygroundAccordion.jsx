import IconArrow from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import _ from 'lodash';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';

import classNames from 'classnames/bind';
import style from './PlaygroundAccordion.module.scss';

const cx = classNames.bind(style);

const calDocumentOptions = (list) => {
  if (!list) return [];
  if (list.length === 0) return [];
  const options = list.map((el) => ({
    ...el,
    label: el.name,
    value: el.id,
  }));
  return options;
};

const calContent = (list, t) => {
  if (list.length === 0) return '0개의 문서';
  return `${t('playground.includedCount.label', {
    name: list[0].label,
    count: list.length - 1,
  })}`;
};

const PlaygroundAccordion = React.memo(() => {
  const { t } = useTranslation();
  const { rag_doc_list } = useSelector(
    (state) => state.llmPlayground.rag,
    _.isEqual,
  );
  const [isOpen, setIsOpen] = useState(false);

  const documentOptions = calDocumentOptions(rag_doc_list);
  const content = calContent(documentOptions, t);

  return (
    <div>
      <div
        className={cx('dropdown-header', isOpen && 'open')}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <div className={cx('content')}>
          <span>{content}</span>
        </div>
        <img
          className={cx('arrow', isOpen && 'open')}
          src={IconArrow}
          alt='arrow'
        />
      </div>
      {isOpen && (
        <ul className={cx('dropdown-list')}>
          {documentOptions.map((item, idx) => (
            <li
              key={item.value}
              id={`dropdown-${item.value}`}
              className={cx(idx > 3 && 'none-bt-border-last-index')}
            >
              {item.frontContent && (
                <div className={cx('front')}>{item.frontContent}</div>
              )}
              <div className={cx('item-txt')}>{item.label}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
});

export default PlaygroundAccordion;
