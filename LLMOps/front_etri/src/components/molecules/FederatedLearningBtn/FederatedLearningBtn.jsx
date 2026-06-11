import { useRouteMatch } from 'react-router-dom';
import { useSelector } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@tango/ui-react';

// Icons
import ShortcutIcon from '@src/static/images/icon/ic-shortcut-white.svg';

// 커스텀 정의
import { PARTNER } from '@src/partner';

// CSS module
import style from './FederatedLearningBtn.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

const FederatedLearningBtn = () => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { workspaceState } = useSelector((state) => ({
    workspaceState: state.workspace,
  }));
  const { id: workspaceId } = match.params;
  const workspaces = workspaceState?.workspaces || [];
  let workspaceName;
  workspaces.map(({ name, id }) => {
    if (Number(workspaceId) === id) {
      workspaceName = name;
    }
    return workspaceName;
  });

  const moveToFederatedLearning = () => {
    window.open(import.meta.env.VITE_REACT_APP_FEDERATED_LEARNING_API_HOST);
  };

  return (
    <div className={cx('wrapper')}>
      <div className={cx('logo-box')}>
        <img
          src={PARTNER[MODE]?.logo?.federatedLearning ?? PARTNER.jp.logo.federatedLearning }
          alt='연합학습'
          className={cx('logo')}
        />
      </div>
      <div className={cx('btn-box')}>
        <Button
          type='primary'
          size='medium'
          onClick={moveToFederatedLearning}
          iconAlign='right'
          icon={ShortcutIcon}
          customStyle={{
            backgroundColor: '#25232a',
            borderColor: '#25232a',
            padding: '12px',
            height: '40px',
          }}
        >
          {t('federatedLearning.label')} {t('open.label')}
        </Button>
      </div>
    </div>
  );
};

export default FederatedLearningBtn;
