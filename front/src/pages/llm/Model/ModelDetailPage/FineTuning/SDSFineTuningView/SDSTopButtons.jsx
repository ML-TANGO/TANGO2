// SDS 두 화면(external / internal VLM)의 상단 버튼줄.
//
// 위치 = `SimpleNav.topButtonList` — 하우스 `TopButtonList` 와 **같은 자리**이고
// 클래스도 하우스 `FineTuning.module.scss` 의 `btn-list` / `message` / `btn` 을
// 그대로 재사용한다(설계 §3-B, §3-D). 그래서 버튼 크기는 그 자리의 하우스 관행인
// `size='l'` 이 기본값이다.
//
// 왜 하우스 `TopButtonList` 를 재사용하지 않는가(설계 §10 / R11·R12):
//   그 컴포넌트의 게이트(`isCalRun`/`isCalCommitLoad`/`isCalStop`/`isCalSystemlog`)는
//   internal `commit_status` 에 하드바인딩돼 있고, external sse-status 의
//   `commit_status.status` 는 null(`idleFineStatus`)이라 **전 버튼이 비활성**된다.
//   MM 은 반대로 하우스보다 더 엄격한 게이트(커밋은 `isDone` 에서만)를 요구한다.
//   → 게이트는 각 뷰가 계산해 descriptor 로 넘기고, 이 컴포넌트는 렌더만 한다.
//
// buttons = [{ key, label, onClick, disabled, type, colorType, size, isLoading }]
//   falsy 항목은 무시된다 → 조건부 버튼을 `cond && {...}` / 삼항으로 쓸 수 있다.
//   `colorType` 미지정 = ButtonV2 기본값 blue(하우스 '실행' 과 동일).
//   `isLoading` 은 선택 — MM 의 '준비 중…' / '저장 중…' 스피너를 그대로 이관하기
//   위한 passthrough 다(미지정 시 undefined = 기존 external 렌더 불변).

import { ButtonV2 } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';

const cx = classNames.bind(style);

function SDSTopButtons({ buttons = [], message = '', messageColor = '' }) {
  return (
    <div className={cx('btn-list')}>
      {message ? (
        <div className={cx('message')} style={{ color: messageColor }}>
          {message}
        </div>
      ) : null}
      <div className={cx('btn')}>
        {buttons.filter(Boolean).map((btn) => (
          <ButtonV2
            key={btn.key ?? btn.label}
            type={btn.type ?? 'solid'}
            size={btn.size ?? 'l'}
            colorType={btn.colorType}
            label={btn.label}
            onClick={btn.onClick}
            disabled={!!btn.disabled}
            isLoading={btn.isLoading}
            style={{ width: '100%' }}
          />
        ))}
      </div>
    </div>
  );
}

export default SDSTopButtons;
