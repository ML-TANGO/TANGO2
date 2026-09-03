// external SDS **비-recipe** 경로의 고급 옵션 패널 — Kubernetes 네임스페이스 +
// 파트너로 그대로 나가는 params JSON.
//
// 왜 하우스 `Advanced` 를 쓰지 않는가(설계 §2-C / §3-E):
//   `Advanced` 는 내용이 "Configuration 파일 업/다운로드" 에 하드바인딩돼 있다 —
//   `unapplicableParams` 상수, `models/option/download/default-configuration`
//   호출, HF git 링크 복사. SDS 의 고급옵션(namespace / raw params)과 의미가 전혀
//   다르고, 범용화하려면 컴포넌트를 갈라야 해서 하우스 고급 탭까지 파급된다.
//   → 별도 패널 신설.
//
// 스타일: 섹션 제목은 하우스 어휘 `cx('title')`, 스택은 하우스 유틸 `cx('flex-16')`,
// 컨트롤(input/textarea/hint)은 기존 external 모듈 클래스를 그대로 재사용해
// **렌더 CSS 델타 0** 을 유지한다(신규 SCSS 규칙 0건).

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSExternalFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

function SDSRawParamsPanel({
  t,
  namespace,
  onChangeNamespace,
  params,
  onChangeParams,
  disabled = false,
}) {
  return (
    <div className={cx('flex-16')}>
      <div>
        <div className={cx('title')}>
          {t('externalTraining.start.namespace.label')}
        </div>
        <input
          className={lx('text-input')}
          type='text'
          value={namespace}
          onChange={(e) => onChangeNamespace(e.target.value)}
          // 비워두면 backend 가 이 인스턴스의 워크스페이스 ns 를 파생한다.
          // 직접 적는 건 cross-workspace 실행이 필요한 admin 용 탈출구.
          placeholder='자동 (워크스페이스 네임스페이스)'
          disabled={disabled}
        />
      </div>
      <div>
        <div className={cx('title')}>
          {t('externalTraining.start.params.label')}
        </div>
        <textarea
          className={lx('params-textarea')}
          value={params}
          onChange={(e) => onChangeParams(e.target.value)}
          disabled={disabled}
          spellCheck={false}
        />
        <div className={lx('hint')}>
          {t('externalTraining.start.params.hint')}
        </div>
      </div>
    </div>
  );
}

export default SDSRawParamsPanel;
