// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';
import { NavLink } from 'react-router-dom';

import ExportButton from '../ExportButton';

// CSS module
import classNames from 'classnames/bind';
import style from './RecordsNav.module.scss';

const cx = classNames.bind(style);

const RecordsNav = ({
  nav: { isExpand },
  navList,
  t,
  handleExcelDownLoad,
  excelDataFormat,
  excelFileName,
  pdfTargetId,
  isExportBtn,
  ...rest
}) => {
  return (
    <div className={cx('nav-box', isExpand && 'expand')} {...rest}>
      <ul className={cx('nav')}>
        {navList.map(({ label, path: pathname }, idx) => (
          <li className={cx('nav-item')} key={idx}>
            <NavLink
              exact
              to={{
                pathname,
              }}
              activeClassName={cx('active')}
            >
              <span className={cx('link-name')}>{t(label)}</span>
              <span className={cx('stick')}></span>
            </NavLink>
          </li>
        ))}
        {isExportBtn && (
          <ExportButton
            excelDownload={handleExcelDownLoad}
            excelDataFormat={excelDataFormat}
            excelFileName={excelFileName}
            pdfTargetId={pdfTargetId}
            style={{ position: 'absolute', right: 0 }}
          />
        )}
      </ul>
    </div>
  );
};

export default connect(({ nav }) => ({ nav }))(withTranslation()(RecordsNav));
