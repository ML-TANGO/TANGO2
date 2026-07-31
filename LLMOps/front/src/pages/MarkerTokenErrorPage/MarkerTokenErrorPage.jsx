import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './MarkerTokenErrorPage.module.scss';

const cx = classNames.bind(style);

/**
 * `/common/token-error` — marker(라벨링) 앱의 토큰 오류 착지 화면.
 *
 * marker FE 는 `ME.01.02 Invalid token` 을 받으면
 * `window.location.href = '/common/token-error'` 로 이동한다. 그런데 marker 는 이
 * 플랫폼에서 `/marker` 베이스네임 아래로 서빙되므로, 베이스네임 없는 절대경로가
 * 플랫폼 SPA 로 떨어져 라우트가 없어 **NotFoundPage(404)** 가 떴다(원인은 marker
 * FE 코드이고 이 저장소에 소스가 없다). 그래서 같은 경로를 우리 쪽에서 받아
 * "무슨 일이 났고 무엇을 하면 되는지"를 알려주는 화면으로 대체한다.
 *
 * 세션이 서로를 무효화하던 근본 원인은 marker BE 에서 수정했다(사용자당 토큰 1행 →
 * USER_TOKEN 다중 세션). 이 화면은 정상 만료(5시간)·로그아웃 등 남은 경우의 착지점.
 */
const MarkerTokenErrorPage = () => {
  const { i18n } = useTranslation();
  const isEn = i18n.language === 'en';

  // 라벨링은 새 창(window.open)으로 열리므로 닫기가 가장 자연스러운 1차 행동.
  // 스크립트로 열지 않은 탭은 close() 가 무시될 수 있어 홈 이동을 함께 제공한다.
  const handleClose = () => {
    window.close();
  };

  const handleHome = () => {
    window.location.href = '/';
  };

  return (
    <div className={cx('cont')}>
      <div className={cx('card')}>
        <h1 className={cx('title')}>
          {isEn ? 'Labeling session expired' : '라벨링 세션이 만료되었습니다'}
        </h1>
        <p className={cx('desc')}>
          {isEn
            ? 'Please reopen labeling from the platform (Data > Labeling).'
            : '플랫폼의 데이터 > 라벨링 메뉴에서 다시 열어주세요.'}
          <span className={cx('hint')}>
            {isEn
              ? 'The labeling session is issued when you enter from the platform, and expires after a period of inactivity.'
              : '라벨링 세션은 플랫폼에서 진입할 때 발급되며, 일정 시간이 지나면 만료됩니다.'}
          </span>
        </p>
        <div className={cx('btn-cont')}>
          <button
            type='button'
            className={cx('btn', 'primary')}
            onClick={handleClose}
          >
            {isEn ? 'Close this tab' : '이 창 닫기'}
          </button>
          <button type='button' className={cx('btn')} onClick={handleHome}>
            {isEn ? 'Go to platform' : '플랫폼으로 이동'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MarkerTokenErrorPage;
