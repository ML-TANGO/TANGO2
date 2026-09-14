import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-toastify';

import {
  getExternalCheckpoints,
  deleteExternalCheckpoint,
  setBestExternalCheckpoint,
} from '@src/apis/llm/model';
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import SimpleNav from '@src/components/molecules/SimpleNav';

import classNames from 'classnames/bind';
import style from './ExternalCheckpointList.module.scss';

const cx = classNames.bind(style);

// 포매터 — CommitList/ModelCommitListItem 의 helper 를 그대로 차용(idiom 통일).
// 값이 null/NaN 이면 '—'. saved_at 은 epoch 초.
const fmtNum = (v, d = 4) => (Number.isFinite(v) ? v.toFixed(d) : '—');
const fmtBytes = (b) => {
  if (!Number.isFinite(b)) return '—';
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB`;
  return `${b} B`;
};
const fmtTs = (sec) => {
  if (!Number.isFinite(sec)) return '—';
  const d = new Date(sec * 1000);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
// 행 식별자 — 체크포인트는 (commit_id, step) 로 유일. 최종 행은 step 센티넬 0 을 쓰는데,
// BE 가 "HF Trainer 실제 step 은 항상 1 이상"을 근거로 충돌 없음을 보장한다(service.py
// _EXTERNAL_FINAL_STEP). 그 불변식이 깨지면 여기 key 와 busy 락 문자열이 같이 흔들린다.
const rowKey = (c) => `${c.commit_id}:${c.step}`;
// 행 라벨 — is_final(커밋 루트 = 학습 완료본)은 step 센티넬 0 이라 'Step 0' 으로 보이면 안 된다.
// 실제 서빙 단위가 이 '최종' 행이다(per-step 은 HF Trainer 덤프라 로더 계약 불만족).
// 최종 행은 커밋마다 하나씩 생기고 행에 커밋명이 따로 없으므로 라벨에 커밋명을 병기한다.
const ckptLabel = (c) =>
  c.is_final ? `최종 · ${c.commit_name}` : `Step ${c.step.toLocaleString()}`;

/**
 * 모델 상세 '체크포인트' 탭 — SDS/external(training_type='external') 모델 전용(P1).
 * 여러 커밋에 흩어진 per-step 체크포인트를 flat 하게 나열하고(BE 가 proj→llm, step
 * 오름차순 정렬), best 지정 · 삭제 · 스토리지 사용량을 보여준다.
 * ETRI 목업(ModelDetailPage MultimodalTabContent '관리' 탭)의 레이아웃/라벨을 따르며,
 * 실 스텝 카드 UI 는 CommitList/ModelCommitListItem 의 idiom 을 재사용한다.
 * 서빙/배포(best→deploy)는 P2 범위 밖.
 */
function ExternalCheckpointList({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const { modelId } = data;

  const [titleName, setTitleName] = useState('');
  const [list, setList] = useState(null); // null=미조회, []=없음
  const [storage, setStorage] = useState(null); // { used_bytes }
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false); // 조회 실패 — 빈 목록("없음")과 구분
  const [busy, setBusy] = useState(null); // `${type}:${cid}:${step}` in-flight (null=idle)

  const reqRef = useRef(0); // 최신 조회만 반영(동시 응답/stale 폐기)
  const mountedRef = useRef(true);
  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // 모델명 (SimpleNav 타이틀용) — Evaluate 탭과 동일하게 lightweight summary 사용.
  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      if (alive && res.status === STATUS_SUCCESS)
        setTitleName(res.result?.name ?? '');
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  const fetchCheckpoints = useCallback(async () => {
    if (!modelId) return;
    // 언마운트 후(핸들러의 await fetchCheckpoints() 경유) setState 방지 — 가드를 head 에.
    if (!mountedRef.current) return;
    const myReq = (reqRef.current += 1);
    setLoading(true);
    let nextList = [];
    let nextStorage = { used_bytes: 0 };
    let ok = false;
    let failMsg = null;
    try {
      const res = await getExternalCheckpoints(modelId);
      const r = (res && res.result) || {};
      if (res && res.status === STATUS_SUCCESS) {
        ok = true;
        if (Array.isArray(r.list))
          nextList = r.list.filter((c) => c && Number.isFinite(c.step));
        if (r.storage && typeof r.storage === 'object') nextStorage = r.storage;
      } else {
        failMsg = (res && res.message) || null;
      }
    } catch (e) {
      failMsg = null;
    }
    // 언마운트됐거나 더 최신 조회가 시작됐으면 폐기.
    if (!mountedRef.current || myReq !== reqRef.current) return;
    setLoadError(!ok);
    if (ok) {
      // 성공 시에만 반영 — 실패로 기존 목록을 빈 배열로 덮어 "없음"처럼 보이지 않게.
      setList(nextList);
      setStorage(nextStorage);
    }
    setLoading(false);
    if (!ok)
      toast.error(
        `체크포인트 목록을 불러오지 못했습니다.${failMsg ? ` (${failMsg})` : ''}`,
      );
  }, [modelId]);

  useEffect(() => {
    fetchCheckpoints();
  }, [fetchCheckpoints]);

  const handleSetBest = async (c) => {
    const cid = parseInt(c.commit_id, 10);
    const step = parseInt(c.step, 10); // 경로 주입 방지 정수화(보안)
    if (
      busy !== null ||
      !Number.isFinite(cid) ||
      !Number.isFinite(step) ||
      !modelId
    )
      return;
    setBusy(`best:${cid}:${step}`);
    try {
      const res = await setBestExternalCheckpoint(modelId, cid, step);
      if (res.status === STATUS_SUCCESS) {
        toast.success(`${ckptLabel(c)} 을(를) BEST 로 지정했습니다`);
        await fetchCheckpoints();
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      if (mountedRef.current) setBusy(null);
    }
  };

  const handleDelete = async (c) => {
    const cid = parseInt(c.commit_id, 10);
    const step = parseInt(c.step, 10); // 경로 주입 방지 정수화(보안)
    if (
      busy !== null ||
      !Number.isFinite(cid) ||
      !Number.isFinite(step) ||
      !modelId
    )
      return;
    // eslint-disable-next-line no-alert
    if (
      typeof window !== 'undefined' &&
      !window.confirm(`체크포인트 ${ckptLabel(c)} 을(를) 삭제할까요?`)
    )
      return;
    setBusy(`del:${cid}:${step}`);
    try {
      const res = await deleteExternalCheckpoint(modelId, cid, step);
      if (res.status === STATUS_SUCCESS) {
        toast.success(`체크포인트 ${ckptLabel(c)} 삭제됨`);
        await fetchCheckpoints(); // 재조회 완료까지 락 유지(레이스/중복 DELETE 방지)
      } else {
        // best/서빙 중 체크포인트 등 가드 실패 — 서버 메시지 그대로 노출.
        errorToastMessage(res.error, res.message);
      }
    } finally {
      if (mountedRef.current) setBusy(null);
    }
  };

  const usedBytes = Number.isFinite(storage?.used_bytes)
    ? storage.used_bytes
    : 0;
  const usedGb = (usedBytes / 1e9).toFixed(1);
  const count = Array.isArray(list) ? list.length : 0;

  return (
    <div id='external-checkpoint-tab' className={cx('checkpoint-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        titleName={titleName}
      />

      <div className={cx('container')}>
        {/* ── 저장된 체크포인트 ── */}
        <section className={cx('section')}>
          <div className={cx('section-label')}>
            저장된 체크포인트 ({count}개)
          </div>

          {loading && list === null ? (
            <div className={cx('empty')}>불러오는 중…</div>
          ) : loadError && count === 0 ? (
            <div className={cx('empty')}>목록을 불러오지 못했습니다.</div>
          ) : count === 0 ? (
            <div className={cx('empty')}>저장된 체크포인트가 없습니다.</div>
          ) : (
            <div className={cx('ckpt-list')}>
              {list.map((c) => {
                const k = rowKey(c);
                const deleting = busy === `del:${c.commit_id}:${c.step}`;
                const besting = busy === `best:${c.commit_id}:${c.step}`;
                return (
                  <div
                    key={k}
                    className={cx('ckpt-item', c.is_best && 'ckpt-item--best')}
                  >
                    <div className={cx('ckpt-top')}>
                      <div className={cx('ckpt-id')}>
                        <span className={cx('ckpt-step')}>{ckptLabel(c)}</span>
                        {Number.isFinite(c.epoch) && (
                          <span className={cx('ckpt-epoch')}>
                            Epoch {c.epoch}
                          </span>
                        )}
                        {c.stage_label && (
                          <span className={cx('ckpt-stage')}>
                            {c.stage_label}
                          </span>
                        )}
                        {c.is_best && (
                          <span
                            className={cx('best-badge')}
                            aria-label='BEST 체크포인트'
                            title='BEST 로 지정된 체크포인트'
                          >
                            <span aria-hidden='true'>★</span> BEST
                          </span>
                        )}
                      </div>
                      <div className={cx('ckpt-actions')}>
                        {!c.is_best && (
                          <button
                            type='button'
                            className={cx('best-btn')}
                            onClick={() => handleSetBest(c)}
                            disabled={busy !== null}
                            aria-label={`${ckptLabel(c)} 을 BEST 로 지정`}
                            title='이 체크포인트를 BEST 로 지정'
                          >
                            {besting ? '지정 중…' : 'Best 지정'}
                          </button>
                        )}
                        {!c.is_final && (
                          <button
                            type='button'
                            className={cx('del-btn')}
                            onClick={() => handleDelete(c)}
                            disabled={busy !== null}
                            aria-label={`체크포인트 ${ckptLabel(c)} 삭제`}
                            title='이 체크포인트 삭제'
                          >
                            {deleting ? '삭제 중…' : '삭제'}
                          </button>
                        )}
                      </div>
                    </div>
                    <div className={cx('ckpt-metrics')}>
                      <span>
                        Loss <b>{fmtNum(c.loss)}</b>
                      </span>
                      <span>
                        Grad Norm <b>{fmtNum(c.grad_norm)}</b>
                      </span>
                      <span>
                        크기 <b>{fmtBytes(c.size_bytes)}</b>
                      </span>
                      <span>
                        저장 시각 <b>{fmtTs(c.saved_at)}</b>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ── 스토리지 사용량 ── (P1 은 used_bytes 만 제공 → 총 할당/비율 표기 안 함) */}
        <section className={cx('section')}>
          <div className={cx('section-label')}>스토리지 사용량</div>
          <div className={cx('storage-box')}>
            <div className={cx('storage-row')}>
              <span className={cx('storage-label')}>체크포인트 사용량</span>
              <span className={cx('storage-val')}>{usedGb} GB</span>
            </div>
            {/* 총 할당량 미제공(P1) → 비율 대신 subtle 인디케이터만. */}
            <div
              className={cx('storage-track', 'storage-track--indeterminate')}
            >
              <div className={cx('storage-shimmer')} />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default ExternalCheckpointList;
