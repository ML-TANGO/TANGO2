// 하우스 파인튜닝 화면(FineTuning.jsx:494–739)의 골격 마크업을 그대로 재현하는
// 얇은 슬롯 컴포넌트. SDS 두 뷰(external / internal VLM)만 사용한다.
//
// 왜 하우스 `FineTuning.jsx` 를 셸로 리팩터하지 않는가(설계 §3-A / §10):
//   하우스(텍스트 LLM 파인튜닝)는 현재 정상 동작하는 최대 트래픽 화면이고, 셸
//   추출은 그 파일의 렌더 트리를 건드린다. SDS 파리티는 "같은 클래스·같은 순서"
//   로 달성되며 하우스 파일 수정은 필요 조건이 아니다(하우스 회귀 0).
//
// ⚠️ 불변식 S1 (설계 §5-B): 이 파일은 SSE 훅(`useSSEStatus`/`useSSEGraph`/
//    `useSSEFinetuningTime`)을 **절대 import 하지 않는다.** 셸이 구독하면 external
//    모델에서 internal SSE(`models/fine-tuning/sse-*/{modelId}`)가 동시에 열려
//    잘못된 상태로 화면이 덮인다. 우측은 이미 만들어진 엘리먼트를 `right` 로 받고,
//    두 뷰는 각자 소스에서 얻은 데이터를 `monitorProps.toMonitorProps()` 로
//    정규화해 주입한다.
// ⚠️ 자체 SCSS 를 만들지 않는다(설계 §3-A) — 하우스와 **물리적으로 같은 클래스**를
//    쓰기 위해 `FineTuning.module.scss` 를 그대로 import 한다. 이 파일 때문에
//    하우스 SCSS 를 수정할 일은 없다(재사용만).
//
// 렌더 결과:
//   div#info-tab.info-tab
//   ├─ SimpleNav (topButtonList = topButtons)
//   ├─ [banner]        — MM commitBanner 자리(Phase 3)
//   ├─ [fullWidthTop]  — external RecipeStepNav 자리(Phase 4)
//   └─ div.box
//      ├─ div.left[.disabled]
//      │  ├─ div.left-top  ← leftSections
//      │  └─ [leftFooter]  — InstanceSetting 자리(Phase 3)
//      └─ div.right        ← right

import SimpleNav from '../../SimpleNav';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';

const cx = classNames.bind(style);

function FineTuningShell({
  navList,
  filteredRest,
  t,
  titleName,
  subTitle,
  topButtons = null,
  banner = null,
  fullWidthTop = null,
  leftSections = null,
  leftFooter = null,
  right = null,
  dimLeft = false,
}) {
  return (
    <div id='info-tab' className={cx('info-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        topButtonList={topButtons}
        titleName={titleName}
        subTitle={subTitle}
      />
      {banner}
      {fullWidthTop}
      <div className={cx('box')}>
        <div className={cx('left', dimLeft && 'disabled')}>
          <div className={cx('left-top')}>{leftSections}</div>
          {leftFooter}
        </div>
        <div className={cx('right')}>{right}</div>
      </div>
    </div>
  );
}

export default FineTuningShell;
