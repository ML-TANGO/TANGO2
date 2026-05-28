import { useState, useCallback, useEffect } from 'react';

import { scrollTo } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './ScrollToTopBtn.module.scss';
const cx = classNames.bind(style);

let timer;
const ScrollToTop = ({ scrollBox }) => {
  const [isScroll, setIsScroll] = useState(false);

  const moveToTop = useCallback(() => {
    if (scrollBox) {
      scrollTo(scrollBox, 0, 300);
    }
  }, [scrollBox]);

  useEffect(() => {
    const onScroll = () => {
      if (!timer) {
        timer = setTimeout(() => {
          timer = null;
          if (scrollBox.scrollTop !== 0) setIsScroll(true);
          else setIsScroll(false);
        }, 200);
      }
    };

    if (scrollBox) {
      scrollBox.addEventListener('scroll', onScroll);
    }
    return () => {
      scrollBox.removeEventListener('scroll', onScroll);
    };
  }, [scrollBox, setIsScroll]);

  return (
    <button
      className={cx('scroll-to-top-btn', isScroll && 'show')}
      onClick={moveToTop}
    >
      <img src='/images/icon/angle-up-blue.svg' alt='scroll to top button' />
      <span>TOP</span>
    </button>
  );
};

export default ScrollToTop;
