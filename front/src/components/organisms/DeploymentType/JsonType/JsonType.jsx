import { useEffect } from 'react';
import { JsonEditor as Editor } from 'jsoneditor-react';
import 'jsoneditor-react/es/editor.min.css';
import ace from 'brace';
import 'brace/mode/json';
import 'brace/theme/monokai';

import { useTranslation } from 'react-i18next';

import GuideIcon from '@src/static/images/icon/setting_guide.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './JsonType.module.scss';
const cx = classNames.bind(style);

const SETTING_GUIDE =
  'https://mousy-blanket-c1e.notion.site/967d2ad4238a4548a578ae09e9e36a64';

function JsonType({
  jsonData,
  jsonDataHandler,
  jsonDataErrorHandler,
  editStatus,
  readOnly,
  innerRef,
}) {
  const { t } = useTranslation();
  const lan = localStorage.getItem('language');

  useEffect(() => {
    if (document.getElementsByClassName('jsoneditor-menu')) {
      // 메뉴 숨기려면 주석 모두 해제
      // document.querySelectorAll('.jsoneditor-menu').forEach(function (val) {
      //   val.style.display = 'none';
      // });
      document.querySelectorAll('.jsoneditor').forEach(function (val) {
        val.style.border = 'none';
      });
      document
        .querySelectorAll('.jsoneditor-transform')
        .forEach(function (val) {
          val.style.display = 'none';
        });
      // document
      //   .getElementsByClassName('jsoneditor-outer')[0]
      //   .style.setProperty('padding-top', 0);
      // document
      //   .getElementsByClassName('jsoneditor-outer')[0]
      //   .style.setProperty('margin', 0);
    }
  }, []);

  return (
    <div>
      <div
        className={cx('jsonType-label', lan === 'en' && 'en-jsonType-label')}
      >
        <p>{t('template.guide.label')}</p>
        <p>{t('template.guide.message.label')}</p>
        <div onClick={() => window.open(SETTING_GUIDE, '_blank')}>
          {t('template.settingGuide.label')}
          <img src={GuideIcon} alt='guideIcon' />
        </div>
      </div>
      <div className={cx(editStatus && 'edit', 'jsonType-contents')}>
        <Editor
          ref={innerRef}
          value={jsonData}
          ace={ace}
          mode={readOnly ? 'view' : 'code'}
          theme='ace/theme/monokai'
          onChange={jsonDataHandler('data')}
          navigationBar={false}
          statusBar={false}
          onValidationError={jsonDataErrorHandler}
          onError={(e) => console.log(e)}
        />
      </div>
    </div>
  );
}

export default JsonType;
