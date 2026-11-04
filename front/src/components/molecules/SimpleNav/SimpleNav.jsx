// 상세 화면 공용 헤더 — 제목(+부제) · 우측 액션 슬롯 · 탭 바.
//   모델 상세(정보/학습/커밋/양자화/체크포인트)와 평가 프로젝트 상세가 같은 마크업을
//   평행 구현으로 갖고 있었다. 공유를 막고 있던 건 마크업이 아니라 **redux 결합**이었다:
//   여기서 state.llmModel.info.name 을 직접 읽고 titleName 보다 우선시켜서, 모델이 아닌
//   화면이 쓰면 제목이 모델명으로 오염됐다. 이제 이름은 titleName 프롭으로만 받는다
//   — 호출부는 자기 데이터의 이름을 명시적으로 넘겨야 한다.
//   `topButtonList` 슬롯의 위치는 여러 화면이 문서화해 온 계약이다(SDSTopButtons 등).
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

import classNames from 'classnames/bind';
import style from './SimpleNav.module.scss';

const cx = classNames.bind(style);

// navList 는 **비어 있을 수 있다** — 탭이 하나뿐이라 탭바가 장식인 화면(평가 프로젝트
//   상세)이 빈 배열을 넘긴다. 예전엔 `if (!navList) return null` 이라 목록이 없으면 제목·
//   부제·액션 버튼까지 통째로 사라졌다: 탭만 지우려던 화면이 헤더를 통째로 잃는 셈이라,
//   호출부는 탭을 없애려고 이 컴포넌트를 버려야 했다. 이제 **목록이 비면 <ul> 만 건너뛰고**
//   제목 줄은 언제나 그린다.
//   warn 은 남긴다 — 빈 배열(의도적으로 탭 없음)과 undefined(넘기는 걸 잊음)는 다른 사건이라
//   후자만 콘솔에 남기고, 렌더는 둘 다 "탭 없는 헤더"로 같게 취급한다. 더는 return 하지
//   않으므로 warn 이 렌더를 좌우하지 않는다.
//   ⚠️ 모델 상세 6 화면은 ModelDetailPage 의 useMemo 가 만든 **4원소 리터럴 배열**을 항상
//   넘긴다(ModelDetailPage.jsx:109 — 조건은 커밋↔체크포인트 원소 교체뿐, 길이는 4로 고정).
//   비거나 undefined 가 되는 경로가 없어 이 분기에 닿지 않으므로 모델 탭바는 그대로다.
function SimpleNav({ navList, topButtonList, titleName, subTitle }) {
  const { t } = useTranslation();
  if (!navList) {
    console.warn('No navList');
  }
  const navItems = Array.isArray(navList) ? navList : [];

  return (
    <div className={cx('nav-box')}>
      <div className={cx('title')}>
        <div className={cx('name')}>
          <div>{titleName}</div>
          {subTitle && <div className={cx('sub-title')}>{subTitle}</div>}
        </div>
        {topButtonList && <div className={cx('btn')}>{topButtonList}</div>}
      </div>
      {navItems.length > 0 && (
        <ul className={cx('nav')}>
          {navItems.map(({ label, path }, idx) => (
            <li className={cx('nav-item')} key={idx}>
              <NavLink exact to={path} activeClassName={cx('active')}>
                <span className={cx('link-name')}>{t(label)}</span>
                <span className={cx('stick')}></span>
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SimpleNav;
