import { useDispatch, useSelector } from 'react-redux';

// Actions
import { userSettingPopup } from '@src/store/modules/headerOptions';

// Components
import UserSettingPopup from './UserSettingsPopup';
import ContextPopupBtn from '../ContextPopupBtn';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserSetting.module.scss';
const cx = classNames.bind(style);

/**
 * 유저 설정 컨텍스트 팝업
 * 기능
 * - 로그아웃
 * - 비밀번호 변경
 * - FB 서비스 메뉴얼 다운로드
 * @param {JSX.Element} children 인자로 받은 JSX 엘리먼트 클릭 시 유저 설정 컨텍스트 팝업 제공
 * @component
 * @example
 *
 * return (
 *  <UserSetting />
 * )
 */
function UserSetting() {
  const dispatch = useDispatch();
  const {
    auth,
    headerOptions: { userSettingPopup: isOpen },
  } = useSelector((state) => ({
    auth: state.auth,
    headerOptions: state.headerOptions,
  }));

  // 로그인한 유저 정보
  const { userName, jpUserName } = auth;

  const popupHandler = () => {
    dispatch(userSettingPopup());
  };

  return (
    <div className={cx('user-setting')}>
      <div data-testid='open-user-context-popup-btn'>
        <ContextPopupBtn isOpen={isOpen} popupHandler={popupHandler}>
          <div className={cx('profile-wrap')}>
            <div className={cx('thumbnail')}>
              <div className={cx('user-initial')}>
                {userName.substr(0, 2).toUpperCase()}
              </div>
            </div>
            <div className={cx('name')} data-testid='user-name'>
              {jpUserName || userName}
            </div>
          </div>
        </ContextPopupBtn>
      </div>
      {isOpen && (
        <UserSettingPopup
          popupHandler={popupHandler}
          userName={userName}
          jpUserName={jpUserName}
        />
      )}
    </div>
  );
}

export default UserSetting;
