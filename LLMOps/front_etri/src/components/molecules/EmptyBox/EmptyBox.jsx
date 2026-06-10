import PropTypes from 'prop-types';
// i18n
import { withTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS Module
import style from './EmptyBox.module.scss';

const cx = classNames.bind(style);

/**
 * 보여줄 정보가 없을 경우 보여주는 컴포넌트
 * @param {object} customStyle 커스텀 스타일을 위한 객체 ex) { display: 'block' }
 * @param {string} text 해당 컴포넌트 중앙에 보여줄 메세지 텍스트
 * @param {function} t 다국어 지원 함수
 * @param {boolean} isBox isBox가 true면 border 스타일을 추가함
 * @component
 * @example
 *  const text = 'Empty data';
 *  return (
 *    <EmptyBox text={text} />
 *  )
 *
 *
 * --
 */
const EmptyBox = ({
  customStyle = {},
  text,
  t,
  isBox = false,
  isRed = false,
}) => {
  return (
    <div
      className={cx('no-data', isBox && 'box', isRed && 'red')}
      style={customStyle}
    >
      {t ? t(text) : 'No Data'}
    </div>
  );
};

EmptyBox.propTypes = {
  customStyle: PropTypes.object,
  text: PropTypes.string,
  t: PropTypes.func,
  isBox: PropTypes.bool,
};

export default withTranslation()(EmptyBox);
