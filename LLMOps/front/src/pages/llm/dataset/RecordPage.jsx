import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { getRecordByKey, recordImageUrl } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import {
  Badge,
  Btn,
  GateRibbon,
  PageHeader,
  SectionHead,
  dsBase,
  useDatasetNav,
} from './components';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 레코드 상세.
 *
 * 이 화면의 목적은 "이 한 건이 왜 이 점수를 받았는가"를 끝까지 따라가는 것이다.
 * 그래서 대화 원문 · 게이트 점수 · 심사와 사람의 판정 이력 · 계보(어느 실행에서 어떤
 * 원본으로 만들었는지)를 한 화면에 둔다.
 *
 * 축과 임계값은 레코드가 아니라 **데이터셋의 프리셋**을 따른다 — 서버가 레코드에
 * 얹어서 준다(`axes`, `thresholds`). FE 가 상수를 들고 있으면 해양 데이터셋에서
 * 범용 축을 그린다.
 */

const REVIEW_LABEL = {
  approved: '승인',
  edited: '수정 후 승인',
  rejected: '거절',
  pending: '대기',
};

const STATE_TONE = { rejected: 'fail', pending: 'warn' };

export default function RecordPage() {
  const { wsId, dsId } = useDatasetNav();
  const { rid } = useParams();

  const [rec, setRec] = useState(null);
  const [failed, setFailed] = useState('');

  const load = useCallback(async () => {
    const res = await getRecordByKey(dsId, rid);
    if (res.status !== STATUS_SUCCESS) {
      setFailed(res.message || '레코드를 불러오지 못했습니다');
      errorToastMessage(res.error, res.message);
      return;
    }
    setFailed('');
    setRec(res.result);
  }, [dsId, rid]);

  useEffect(() => {
    load();
  }, [load]);

  if (failed || !rec) {
    return (
      <div className={style.page}>
        <PageHeader
          title={rid}
          back={{ to: `${dsBase(wsId, dsId)}/review`, label: '돌아가기' }}
        />
        <div className={common['card-pad']}>
          <span className={common.prose}>{failed || '불러오는 중…'}</span>
        </div>
      </div>
    );
  }

  const lineage = rec.lineage || {};
  // 원본 이미지는 서버가 레코드 id 로 찾아 준다. 화면이 run_id·경로를 조립하지 않는다
  // (썸네일은 실행마다 일부만 만들어져 점수 낮은 레코드에서 오히려 비어 있다).
  // asset_ref 가 없으면 이미지를 지어내지 않고 그 사실을 적는다.
  const thumb = rec.id && rec.asset_ref ? recordImageUrl(dsId, rec.id) : null;

  const lineageRows = [
    ['데이터 유형', rec.capability],
    ['분할', rec.split],
    ['원본 자산', rec.asset_ref],
    ...Object.entries(lineage).map(([k, v]) => [
      k,
      typeof v === 'object' ? JSON.stringify(v) : String(v),
    ]),
  ].filter(([, v]) => v !== null && v !== undefined && v !== '');

  return (
    <div className={style.page}>
      <PageHeader
        title={rec.record_key}
        back={{ to: `${dsBase(wsId, dsId)}/review`, label: '돌아가기' }}
        actions={
          <Badge tone={STATE_TONE[rec.review_state] || 'pass'} size='lg'>
            {REVIEW_LABEL[rec.review_state] || rec.review_state}
          </Badge>
        }
      />

      <div className={style['record-detail-grid']}>
        <div className={common['stack-lg']}>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            {thumb ? (
              <span className={style['review-shot']}>
                <img
                  src={thumb}
                  alt={rec.record_key}
                  style={{ width: '100%', borderRadius: 8 }}
                />
              </span>
            ) : (
              <span className={common.prose}>
                이 레코드의 원본 이미지를 찾을 수 없습니다.
              </span>
            )}
          </div>

          <div className={common.stack}>
            <SectionHead>대화</SectionHead>
            <div className={[common['card-pad'], common.stack].join(' ')}>
              <span className={style.turn}>
                <span className={style['turn-role']}>user</span>
                <span className={style['turn-text']}>
                  <span className={common.num} style={{ color: '#2d76f8' }}>
                    [이미지]
                  </span>{' '}
                  {rec.question}
                </span>
              </span>
              <span className={[style.turn, style['turn-divider']].join(' ')}>
                <span className={style['turn-role']}>assistant</span>
                <span className={[style['turn-text'], common.mute].join(' ')}>
                  {rec.answer}
                </span>
              </span>
            </div>
          </div>
        </div>

        <div className={common['stack-lg']}>
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>
              게이트 리본
            </span>
            <GateRibbon
              axes={(rec.axes || []).map((a) => ({
                k: a.key,
                label: a.label,
                short: a.short,
              }))}
              scores={rec.scores || {}}
              thresholds={rec.thresholds || {}}
              size='lg'
            />
          </div>

          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>
              판정 이력
            </span>
            {rec.judge_comment && (
              <span className={[common.note, common['note-fail']].join(' ')}>
                <span className={[common.num, common['note-title']].join(' ')}>
                  심사
                </span>
                <span className={common['note-body']}>{rec.judge_comment}</span>
              </span>
            )}
            {(rec.reviews || []).map((rv) => (
              <span
                key={rv.id ?? `${rv.reviewer}-${rv.create_datetime}`}
                className={[common.note, common['note-info']].join(' ')}
              >
                <span className={[common.num, common['note-title']].join(' ')}>
                  사람 · {rv.reviewer || '—'}
                </span>
                <span className={common['note-body']}>
                  {REVIEW_LABEL[rv.verdict] || rv.verdict}
                  {rv.taxonomy ? ` · ${rv.taxonomy}` : ''}
                </span>
              </span>
            ))}
            {!rec.judge_comment && (rec.reviews || []).length === 0 && (
              <span className={common.prose}>아직 판정 기록이 없습니다.</span>
            )}
          </div>

          {/* 계보 — 나중에 "이 레코드는 어디서 왔나"를 되짚을 수 있어야 프롬프트를 고친다. */}
          <div className={[common['card-pad'], common.stack].join(' ')}>
            <span className={common.body} style={{ fontFamily: 'SpoqaB' }}>
              계보
            </span>
            {lineageRows.map(([k, v]) => (
              <span key={k} className={style['lineage-row']}>
                <span className={style['lineage-key']}>{k}</span>
                <span className={style['lineage-value']}>{v}</span>
              </span>
            ))}
          </div>

          <div
            className={[common['card-pad'], common['row-between']].join(' ')}
          >
            <span className={common.prose}>
              이 레코드를 판정하려면 검수 화면에서 진행합니다.
            </span>
            <Btn
              size='md'
              fill='outline'
              tone='gray'
              onClick={() => window.history.back()}
            >
              검수로 →
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
