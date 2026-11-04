import { useTranslation } from 'react-i18next';

import ToolCardList from './ToolCardList';
import ToolCreateButton from './ToolCreateButton';

import classNames from 'classnames/bind';
import style from './IntegratedTool.module.scss';

const cx = classNames.bind(style);

function IntegratedTool({ trainingType }) {
  const { t } = useTranslation();

  return (
    <div className={cx('integrated-tool-box')}>
      <h2 className={cx('tool-title')}>{t('developTool.label')}</h2>
      {trainingType && trainingType !== 'built-in' && (
        <div className={cx('add-btn-box')}>
          <ToolCreateButton type={7} />
          <ToolCreateButton type={1} />
          <ToolCreateButton type={4} />
        </div>
      )}
      <ToolCardList />
    </div>
  );
}

export default IntegratedTool;
