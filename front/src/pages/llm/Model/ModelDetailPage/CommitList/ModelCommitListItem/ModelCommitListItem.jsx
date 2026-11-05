import {
  getModelsCommitModels,
  getCommitCheckpoints,
  deleteCommitCheckpoint,
  promoteCommitCheckpoint,
} from '@src/apis/llm/model';
import InfoIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import * as echarts from 'echarts';
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { toast } from 'react-toastify';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ModelCommitListItem.module.scss';

const cx = classNames.bind(style);

// 체크포인트 카드 표시용 포매터(파인튜닝 뷰에서 이전 — Phase 2-C).
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

function DynamicLineCharts({ resultLog, epoch }) {
  const chartRefs = useRef([]);

  useLayoutEffect(() => {
    // 그래프 초기화
    if (resultLog && Object.keys(resultLog).length > 0) {
      Object.entries(resultLog).forEach(([key, value], index) => {
        const chartContainer = chartRefs.current[index];
        if (chartContainer && value.steps && value.values) {
          const minValue =
            Math.trunc(Math.min(...value.values) * 0.95 * 100) / 100;
          // const rawMinValue = Math.min(...value.values);
          // const minValue =
          //   rawMinValue < 0 ? 0 : parseFloat(rawMinValue.toFixed(2));
          const chart = echarts.init(chartContainer);
          const option = {
            tooltip: { trigger: 'axis' },
            grid: {
              top: 24,
              right: 24,
              bottom: 24,
              left: 24,
              containLabel: true,
            },
            xAxis: { type: 'category', data: value.steps, boundaryGap: false },
            yAxis: { type: 'value', min: minValue },
            series: [
              {
                type: 'line',
                data: value.values,
                smooth: true,
                lineStyle: { width: 2 },
                itemStyle: { color: '#002f77' },
              },
            ],
          };
          chart.setOption(option);

          const resizeObserver = new ResizeObserver(() => {
            chart.resize();
          });
          resizeObserver.observe(chartContainer);

          // Cleanup
          return () => {
            resizeObserver.disconnect();
          };
        }
      });
    }
  }, [resultLog]);

  return (
    <div className={cx('chart-grid')}>
      {resultLog &&
        Object.entries(resultLog).map(([key], index) => (
          <div key={key} className={cx('chart-item')}>
            <div className={cx('chart-title')}>{key}</div>
            <div
              ref={(el) => (chartRefs.current[index] = el)}
              className={cx('chart-container')}
            />
            <div className={cx('epoch')}>
              <img src={InfoIcon} alt='icon' />1 Epoch = {epoch} steps
            </div>
          </div>
        ))}
    </div>
  );
}

function ModelCommitListItem({ data }) {
  const { cId, t } = data;

  const [info, setInfo] = useState(null);

  // 이 커밋(버전)에 귀속된 체크포인트 스냅샷(Phase 2-C). null=미조회, []=없음.
  const [ckpts, setCkpts] = useState(null);
  const [ckptLoading, setCkptLoading] = useState(true);   // 첫 조회 전 빈 박스 깜빡임 방지
  const [ckptDeleting, setCkptDeleting] = useState(null); // 삭제 in-flight step(null=idle; step:0 엣지 위해 0 sentinel 금지)
  const [promoting, setPromoting] = useState(null);       // promote in-flight step(null=idle; step:0 엣지 위해 0 sentinel 금지)
  const ckptReqRef = useRef(0);                           // 최신 조회만 반영(동시 응답/stale 폐기)
  const ckptMountedRef = useRef(true);
  useEffect(() => () => { ckptMountedRef.current = false; }, []);

  const getInfo = useCallback(async () => {
    const res = await getModelsCommitModels(cId);

    const { result, status, error, message } = res;
    if (status === STATUS_SUCCESS) {
      setInfo(result);
    } else {
      errorToastMessage(error, message);
    }
  }, [cId]);

  useEffect(() => {
    getInfo();
  }, [getInfo]);

  const modelId = info?.model_id;

  // 커밋 스냅샷 체크포인트 조회 — info(모델 id) 로딩 후 실행. 커밋은 frozen 이라 1회 조회면 충분.
  const fetchCheckpoints = useCallback(async () => {
    if (!modelId || !cId) return;
    const myReq = (ckptReqRef.current += 1);    // 이 조회의 토큰
    setCkptLoading(true);
    let list = [];
    try {
      const res = await getCommitCheckpoints(modelId, cId);
      const r = (res && res.result) || {};
      // 비-객체/누락 엔트리는 렌더 크래시 방지 위해 제거, 정상 응답만 채택.
      if (res && res.status === STATUS_SUCCESS && Array.isArray(r.list)) {
        list = r.list.filter((c) => c && Number.isFinite(c.step));
      }
    } catch (e) {
      list = [];
    }
    // 언마운트됐거나 더 최신 조회가 시작됐으면 폐기 — setState 안 함.
    if (!ckptMountedRef.current || myReq !== ckptReqRef.current) return;
    setCkpts(list);
    setCkptLoading(false);
  }, [modelId, cId]);

  useEffect(() => { fetchCheckpoints(); }, [fetchCheckpoints]);

  const handleDeleteCkpt = async (step) => {
    const s = parseInt(step, 10);               // 서버 응답값이지만 경로 주입 방지 위해 정수화(보안)
    if (ckptDeleting !== null || !Number.isFinite(s) || !modelId) return;   // null=idle (step:0 엣지 안전)
    // eslint-disable-next-line no-alert
    if (typeof window !== 'undefined' && !window.confirm(`체크포인트 step ${s} 을(를) 삭제할까요?`)) return;
    setCkptDeleting(s);
    try {
      const res = await deleteCommitCheckpoint(modelId, cId, s);
      if (res.status === STATUS_SUCCESS) {
        toast.success(`체크포인트 step ${s} 삭제됨`);
        await fetchCheckpoints();    // 재조회 완료까지 락 유지(레이스/중복 DELETE 방지)
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      setCkptDeleting(null);
    }
  };

  // promote — 이 step 체크포인트를 새 버전 `<commit>-step<step>` 으로 적용(LoRA cat 재머지, 비파괴).
  const handlePromote = async (step) => {
    const s = parseInt(step, 10);               // 경로 주입 방지 정수화(보안)
    if (promoting !== null || ckptDeleting !== null || !Number.isFinite(s) || !modelId) return;
    // eslint-disable-next-line no-alert
    if (typeof window !== 'undefined' && !window.confirm(`이 커밋의 step ${s} 체크포인트를 새 버전으로 적용할까요? (새 커밋이 생성됩니다)`)) return;
    setPromoting(s);
    try {
      const res = await promoteCommitCheckpoint(modelId, cId, s);
      if (res.status === STATUS_SUCCESS && res.result) {
        toast.success(`step ${s} 적용 시작 — 새 버전이 커밋 목록에 추가됩니다`);
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      setPromoting(null);
    }
  };

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>
        {info?.name ?? '-'}
        <span>{info?.model_name ?? '-'}</span>
      </div>
      <div className={cx('top')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitName.label')}</div>
          <div className={cx('value')}>{info?.name ?? '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitMessage.label')}</div>
          <div className={cx('value')}>
            {!info?.commit_message ? '-' : info.commit_message}
          </div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('writer.label')}</div>
          <div className={cx('value')}>{info?.create_user_name ?? '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('commitDate.label')}</div>
          <div className={cx('value')}>{info?.commit_datetime ?? '-'}</div>
        </div>
      </div>
      <div className={cx('graph')}>
        {info?.result_log && (
          <DynamicLineCharts
            resultLog={info.result_log}
            epoch={info.steps_per_epoch}
          />
        )}
      </div>

      {/* 이 커밋(버전)에 귀속된 체크포인트 스냅샷(Phase 2-C) — step별 어댑터 후보. 메트릭·★best·삭제.
          커밋 시 commit_checkpoints/<commit> 로 보존됨(학습 화면에서 이전). */}
      <div className={cx('ckpt-section')}>
        <div className={cx('ckpt-head')}>
          <div className={cx('ckpt-title')}>체크포인트</div>
          {ckpts && ckpts.length > 0 && (
            <span className={cx('ckpt-usage')}>
              {fmtBytes(ckpts.reduce((s, c) => s + (Number.isFinite(c.size_bytes) ? c.size_bytes : 0), 0))} · {ckpts.length}개
            </span>
          )}
        </div>
        {ckpts === null ? (
          <div className={cx('ckpt-empty')}>{ckptLoading ? '불러오는 중…' : ''}</div>
        ) : ckpts.length === 0 ? (
          <div className={cx('ckpt-empty')}>이 커밋에 저장된 체크포인트가 없습니다.</div>
        ) : (
          <>
            <div className={cx('ckpt-list')}>
              {ckpts.map((c) => (
                <div key={c.step} className={cx('ckpt-item', c.is_best && 'ckpt-item--best')}>
                  <div className={cx('ckpt-top')}>
                    <div className={cx('ckpt-id')}>
                      <span className={cx('ckpt-step')}>Step {c.step.toLocaleString()}</span>
                      {Number.isFinite(c.epoch) && <span className={cx('ckpt-epoch')}>Epoch {c.epoch.toFixed(2)}</span>}
                      {c.is_best && (
                        <span className={cx('best-badge')} aria-label='BEST 체크포인트 (eval/loss 최저)' title='eval/loss 최저(과적합 전)'>
                          <span aria-hidden='true'>★</span> BEST
                        </span>
                      )}
                    </div>
                    <div className={cx('ckpt-actions')}>
                      {!c.is_best && (
                        <button type='button' className={cx('ckpt-apply')} onClick={() => handlePromote(c.step)}
                          disabled={promoting !== null || ckptDeleting !== null}
                          aria-label={`체크포인트 step ${c.step.toLocaleString()} 을 새 버전으로 적용`}
                          title='이 체크포인트를 새 버전(커밋)으로 적용'>
                          {promoting === c.step ? '적용 중…' : '이 step으로 적용'}
                        </button>
                      )}
                      <button type='button' className={cx('ckpt-del')} onClick={() => handleDeleteCkpt(c.step)}
                        disabled={ckptDeleting === c.step || promoting !== null}
                        aria-label={`체크포인트 step ${c.step.toLocaleString()} 삭제`}
                        title='이 체크포인트 삭제'>
                        {ckptDeleting === c.step ? '삭제 중…' : '삭제'}
                      </button>
                    </div>
                  </div>
                  <div className={cx('ckpt-metrics')}>
                    <span>eval/loss <b>{fmtNum(c.eval_loss)}</b></span>
                    <span>loss <b>{fmtNum(c.loss)}</b></span>
                    <span>grad <b>{fmtNum(c.grad_norm, 3)}</b></span>
                    <span>크기 <b>{fmtBytes(c.size_bytes)}</b></span>
                    <span>저장 <b>{fmtTs(c.saved_at)}</b></span>
                  </div>
                </div>
              ))}
            </div>
            <div className={cx('ckpt-hint')}>★ BEST = eval/loss 최저(과적합 전) 체크포인트(이 커밋에 반영됨). 다른 step을 “이 step으로 적용”하면 새 버전 커밋으로 만들어집니다. loss/grad 는 로깅 주기상 인접 step 값일 수 있습니다.</div>
          </>
        )}
      </div>
    </div>
  );
}

export default ModelCommitListItem;
