// CSS Module
import classNames from 'classnames/bind';
import style from './PageTitle.module.scss';

const cx = classNames.bind(style);

/**
 * 페이지 타이틀 컴포넌트
 * @component
 * @example
 *
 * return (
 *  <PageTitle>
 *    title
 *  </PageTitle>
 * );
 *
 *
 *
 * -
 */
const PageTitle = ({ children, desc, ...rest }) => {
  return (
    <h2 className={cx('page-title')} {...rest}>
      <span>{children}</span>
      <span className={cx('page-desc')}>{desc}</span>
    </h2>
  );
};

export default PageTitle;
