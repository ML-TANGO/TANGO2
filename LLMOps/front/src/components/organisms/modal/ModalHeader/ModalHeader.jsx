// CSS Module
import classNames from 'classnames/bind';
import style from './ModalHeader.module.scss';
const cx = classNames.bind(style);

/**
 * 모달 헤더 컴포넌트 (Organisms)
 * @param {{ title: string | undefined }} props
 * @component
 * @example
 *
 * return (
 *    <ModalHeader title='Training Create' />
 * );
 */
function ModalHeader({ title }) {
  return <h2 className={cx('title')}>{title}</h2>;
}

export default ModalHeader;
