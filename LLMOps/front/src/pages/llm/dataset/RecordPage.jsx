import React from 'react';
import { useParams } from 'react-router-dom';

import {
  Badge, Btn, Checkbox, Frame, GateRibbon, PageHeader, SectionHead, dsBase, useDatasetNav,
} from './components';
import { RECORDS } from './mock';
import { SHOTS } from './lib/frames';
import { AXES, THRESHOLDS } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 레코드 상세.
 *
 * 이 화면의 목적은 "이 한 건이 왜 이 점수를 받았는가"를 끝까지 따라가는 것이다.
 * 그래서 대화 원문 · 게이트 점수 · 심사와 사람의 판정 이력 · 계보(어느 모델이 어떤
 * 프롬프트로 어느 원본에서 만들었는지)를 한 화면에 둔다.
 */
export default function RecordPage() {
  const { wsId, dsId, go } = useDatasetNav();
  const { rid } = useParams();

  const i = Math.max(0, RECORDS.findIndex((r) => r.id === rid));
  const r = RECORDS[i];

  const step = (d) => {
    const next = RECORDS[(i + d + RECORDS.length) % RECORDS.length];
    go(`/record/${next.id}`);
  };

  const lineage = [
    ['origin', 'synthetic'],
    ['생성 모델', 'Qwen3-VL-8B · apache-2.0'],
    ['프롬프트', 'docqa_v4'],
    ['심사 모델', 'InternVL3-8B · mit'],
    ['데이터', 'asset_0021 · doc_0007 p.12'],
    ['데이터 유형', r.cap],
  ];

  return (
    <div className={style.page}>
      <PageHeader
        title={r.id}
        back={{ to: `${dsBase(wsId, dsId)}/review`, label: '돌아가기' }}
        actions={(
          <span className={style.toolbar}>
            <Btn size="md" fill="outline" tone="gray" onClick={() => step(-1)}>이전</Btn>
            <Btn size="md" fill="outline" tone="gray" onClick={() => step(1)}>다음</Btn>
          </span>
        )}
      />

      <div className={style['record-detail-grid']}>
        <div className={common['stack-lg']}>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={style['review-shot']}>
              <Frame spec={SHOTS[r.shot]} ariaLabel={r.id} />
            </span>
            <Checkbox checked onChange={() => {}} label="영역 좌표 오버레이" />
          </div>

          <div className={common.stack}>
            <SectionHead>대화</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span className={style.turn}>
                <span className={style['turn-role']}>user</span>
                <span className={style['turn-text']}>
                  <span className={common.num} style={{ color: '#2d76f8' }}>[이미지]</span> {r.q}
                </span>
              </span>
              <span className={[style.turn, style['turn-divider']].join(' ')}>
                <span className={style['turn-role']}>assistant</span>
                <span className={[style['turn-text'], common.mute].join(' ')}>{r.a}</span>
              </span>
              <span className={[style.turn, style['turn-divider']].join(' ')}>
                <span className={style['turn-role']}>좌표</span>
                <span className={common.stack} style={{ gap: 6 }}>
                  <span className={[common.num, common.cell].join(' ')}>[0.12, 0.34, 0.20, 0.08]</span>
                  <span className={common['cell-mute']}>ref: 합계 칼럼</span>
                </span>
              </span>
            </div>
          </div>
        </div>

        <div className={common['stack-lg']}>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>게이트 리본</span>
            <GateRibbon axes={AXES} scores={r.s} thresholds={THRESHOLDS} size="lg" />
          </div>

          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>판정 이력</span>
            <span className={[common.note, common['note-fail']].join(' ')}>
              <span className={[common.num, common['note-title']].join(' ')}>심사 · InternVL3-8B</span>
              <span className={common['note-body']}>{r.judge}</span>
            </span>
            <span className={[common.note, common['note-info']].join(' ')}>
              <span className={[common.num, common['note-title']].join(' ')}>사람 · gukjin</span>
              <span className={common['note-body']}>{r.tax ? `거절 · ${r.tax}` : '승인 (수정 없음)'}</span>
            </span>
          </div>

          {/* 계보 — 나중에 "이 레코드는 어디서 왔나"를 되짚을 수 있어야 프롬프트를 고친다. */}
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>계보</span>
            {lineage.map(([k, v]) => (
              <span key={k} className={style['lineage-row']}>
                <span className={style['lineage-key']}>{k}</span>
                <span className={style['lineage-value']}>{v}</span>
              </span>
            ))}
          </div>

          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>소속 데이터셋</span>
            <span className={style.membership}>
              {[['v0.3.1', 'train', 'primary'], ['v0.2.0', 'test', 'gray']].map(([v, s, tone]) => (
                <span key={v} className={style['membership-chip']}>
                  <span className={style['membership-ver']}>{v}</span>
                  <Badge tone={tone}>{s}</Badge>
                </span>
              ))}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
