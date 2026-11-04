import { useRouteMatch } from 'react-router-dom';
import { useSelector } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';

// Icons
import ShortcutIcon from '@src/static/images/icon/ic-shortcut-white.svg';

// 커스텀 정의
import { PARTNER } from '@src/partner';

// CSS module
import style from './MarkerBtn.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

const MarkerBtn = () => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const auth = useSelector((state) => state.auth);
  const { userName } = auth;
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
  const token = sessionStorage.getItem('token');
  const session = sessionStorage.getItem('loginedSession');

  const moveToMarker = () => {
    window.open(
      `${
        import.meta.env.VITE_REACT_APP_MARKER_API_HOST
      }auth?user=${userName}&token=${token}&session=${session}&workspaceId=${workspaceId}&workspaceName=${workspaceName}`,
    );
  };

  return (
    <div className={cx('wrapper')}>
      <div className={cx('logo-box')}>
        <img
          src={PARTNER[MODE]?.logo?.marker ?? PARTNER.jp.logo.marker }
          alt='데이터 어노테이션 도구'
          className={cx('logo')}
        />
        <label>{t('dataAnnotationTool.label')}</label>
      </div>
      <div className={cx('btn-box')}>
        <Button
          type='primary'
          size='medium'
          onClick={moveToMarker}
          iconAlign='right'
          icon={ShortcutIcon}
          customStyle={{
            backgroundColor: '#002f77',
            borderColor: '#002f77',
            padding: '12px',
            height: '40px',
          }}
        >
          {t('open.label')}
        </Button>
      </div>
    </div>
  );
};

export default MarkerBtn;
