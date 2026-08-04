// SDS 두 화면(external / internal VLM) 우측 모니터의 **요약 카드**.
//
// 왜 필요한가(설계 §3-B R열 / R7):
//   하우스 `FineTuningGraph` 는 진행률(floor)·경과·남은시간·차트만 렌더한다. 상태
//   배지 / Loss / Grad Norm / Epoch / 진행 바 / 실패 사유가 없고, `canRenderTime` 이
//   `status==='running'` 을 요구해 done·error 에서는 시간 블록조차 사라진다.
//   → `FineTuningGraph` 를 고치지 않고(하우스 회귀 0) 그 **위에 얹어** 보존한다.
//
// ⚠️ 순수 표시 컴포넌트: SSE 훅을 import 하지 않고(설계 §5-B 불변식 S1), 파생·게이트
//    계산도 하지 않는다. 뷰가 계산한 값을 받아 그리기만 한다. 특히 MM 의
//    `isDone → 100%` 보정(불변식 S6)은 **뷰에 남기고** 여기서는 받은 값을 그대로 쓴다
//    (external 은 그 보정이 없으며 그 동작 차이를 그대로 보존해야 한다).
//
// 클래스는 MM 이 쓰던 것을 그대로 유지(`train-control`/`train-stats`/`stat-card`/
// `prog-track`/`train-warn`/`train-hint`)해 렌더 CSS 델타 0. 섹션 제목만 SDS 고유
// `section-label` → 하우스 어휘 `cx('title')` 로 치환(설계 §3-D).

import { Badge } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../FineTuning.module.scss';
import localStyle from './SDSFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

// 상태 → 조나단 Badge type 매핑(플랫폼 디자인시스템 재사용).
const BADGE_TYPE = {
  running: 'blue',
  pending: 'yellow',
  installing: 'yellow',
  done: 'green',
  error: 'red',
  stop: 'gray',
  idle: 'gray',
};

// 학습 상태 배지(sse-status). 버튼만으론 완료/실패/중지를 구분 못 해 사용자가 결과를
// 알 수 없던 문제.
//
// 값이 같은 기존 키를 재사용하므로 `externalTraining.status.*` 와
// `externalTraining.recipe.status.*` 두 계열이 섞인다(전자의 error='오류'·pending='대기'
// 는 이 배지의 문구와 다르고, 후자의 running='실행 중' 도 다르다). 새 키는 대응 값이
// 아예 없는 stop 하나뿐이다.
const STATUS_META = {
  running: { labelKey: 'externalTraining.status.running', cls: 'running' },
  done: { labelKey: 'externalTraining.status.done', cls: 'done' },
  error: { labelKey: 'externalTraining.recipe.status.error', cls: 'error' },
  stop: { labelKey: 'externalTraining.status.stopped', cls: 'stop' },
  pending: {
    labelKey: 'externalTraining.recipe.status.pending',
    cls: 'pending',
  },
  installing: {
    labelKey: 'externalTraining.recipe.status.pending',
    cls: 'pending',
  },
};

// `control-head` 는 flex row(align-items:center) 라 하우스 `.title` 의
// margin-bottom:16px 이 배지와의 수직 정렬을 흐트린다 → 이 자리에서만 0.
const headTitleStyle = { marginBottom: 0 };

/**
 * @param t       i18next t (호출부 주입 — SSE 훅과 마찬가지로 이 컴포넌트는 자체
 *                구독/획득을 하지 않고 뷰가 가진 것을 받는다)
 * @param label   섹션 제목(하우스 `cx('title')`)
 * @param status  sse-status 의 fine_tuning_status.status 문자열
 * @param reason  실패 사유(뷰가 error 게이트를 통과시킨 값만 넘긴다)
 * @param stats   [{ label, value }] — `train-stats` 그리드는 4열 고정
 * @param percent 진행 바 width(숫자 %)
 * @param hints   하단 안내 문자열 배열(falsy 항목은 무시)
 */
function SDSMonitorSummary({
  t,
  label,
  status,
  reason = null,
  stats = [],
  percent = 0,
  hints = [],
}) {
  const meta = STATUS_META[status];

  return (
    <section className={lx('section')}>
      <div className={lx('control-head')}>
        <div className={cx('title')} style={headTitleStyle}>
          {label}
        </div>
        {meta && (
          <Badge
            label={t(meta.labelKey)}
            type={BADGE_TYPE[meta.cls] || 'gray'}
            size='sm'
          />
        )}
      </div>
      {reason ? (
        <div className={lx('train-warn')}>
          {t('externalTraining.failReason.label')}: {reason}
        </div>
      ) : null}
      <div className={lx('train-control')}>
        <div className={lx('train-stats')}>
          {stats.map((stat) => (
            <div key={stat.label} className={lx('stat-card')}>
              <span className={lx('stat-label')}>{stat.label}</span>
              <span className={lx('stat-val')}>{stat.value}</span>
            </div>
          ))}
        </div>
        <div className={lx('prog-track')}>
          <div className={lx('prog-fill')} style={{ width: `${percent}%` }} />
        </div>
        {hints.filter(Boolean).map((hint) => (
          <div key={hint} className={lx('train-hint')}>
            {hint}
          </div>
        ))}
      </div>
    </section>
  );
}

export default SDSMonitorSummary;
