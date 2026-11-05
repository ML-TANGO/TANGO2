import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './CreateCard.module.scss';
const cx = classNames.bind(style);

function CreateCard({ onClick }) {
  const { t } = useTranslation();
  return (
    <div
      className={cx('create-card')}
      data-testid='open-create-deployment-modal-btn'
      onClick={onClick}
    >
      <div className={cx('inner-box')}>
        <div className={cx('plus')}></div>
        <span className={cx('text')}>{t('newDeployment.label')}</span>
      </div>
    </div>
  );
}

export default CreateCard;
