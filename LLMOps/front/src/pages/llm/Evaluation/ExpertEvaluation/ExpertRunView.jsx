import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, InputText, Loading } from '@jonathan/ui-react';

import ContentBox from '@src/components/molecules/ContentBox';
import EmptyBox from '@src/components/molecules/EmptyBox';

import CsvTable from './components/CsvTable';
import ExpertCompletionBanner from './components/ExpertCompletionBanner';
import ExpertProgressHeader from './components/ExpertProgressHeader';
import ExpertPromptBox from './components/ExpertPromptBox';
import ExpertSampleImage from './components/ExpertSampleImage';
import GenPromptBox from './components/GenPromptBox';
import StarRating from './components/StarRating';

import {
  getExpertResult,
  getExpertSamples,
  inferExpertSample,
  submitExpertRating,
} from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ExpertEvaluation.module.scss';

const cx = classNames.bind(style);

// 코멘트 의무화 임계 — 이 점수 이하로 매기면 사유(코멘트)를 반드시 남겨야 한다.
// 낮은 점수는 "왜 낮은지"가 재학습·모델 개선의 실제 신호이므로 근거 없는 감점을 막는다.
const COMMENT_REQUIRED_MAX_SCORE = 3;

// 현재 채점이 '코멘트 미입력 상태의 낮은 점수'인가 — 별점 확정 보류·다음 잠금의 단일 판정.
const needsComment = (rating) =>
  !!rating &&
  rating.score != null &&
  rating.score <= COMMENT_REQUIRED_MAX_SCORE &&
  !(rating.comment || '').trim();

// 전문가 run 상세 뷰 (P4). 셋업 뷰 없음 — 모델·데이터셋은 프로젝트에서 상속, 세션은 이미
// "세션 시작"(startExpert)으로 생성됨. (modelId, jobId) 로 진입.
//   재개(P7): getExpertSamples 로 samples/expert_prompt/이전 채점 복원 + getExpertResult 로
//   진행/집계 seed → 이미 채점된 샘플은 별점·코멘트·감사줄이 그대로 보인다. (BE 배관 기존재, FE 배선만.)
//   채점: submitExpertRating (낙관적+dedup+롤백), 이전/다음 단일항목 네비, 완료 시 StarRating 비활성.
const ExpertRunView = ({ modelId, jobId, onExit }) => {
  const { t } = useTranslation();
  const mId = Number(modelId);

  const [session, setSession] = useState(null); // { samples, expert_prompt, total }
  const [ratings, setRatings] = useState({}); // idx → { score, comment, rater, ratedAt, count, savedScore, savedComment }
  const [progress, setProgress] = useState(null); // { rated, total, avg_score, distribution, completed }
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [infering, setInfering] = useState({}); // idx → bool (VLM 지연 실추론 로딩 스피너)
  const [attempted, setAttempted] = useState({}); // idx → bool (1회 시도 표시 — 실패해도 재시도 X)

  // 재개 배선 — 마운트 시 세션 샘플 + 이전 채점 + 진행/집계 복원.
  useEffect(() => {
    let active = true;
    setLoading(true);
    setNotFound(false);
    setInfering({}); // 세션 재로드 시 이전 세션의 로딩/시도 플래그 초기화(idx 재사용 오탐 방지)
    setAttempted({});
    (async () => {
      const [sRes, rRes] = await Promise.all([
        getExpertSamples(mId, jobId),
        getExpertResult(mId, jobId),
      ]);
      if (!active) return;
      if (sRes.status !== STATUS_SUCCESS || !sRes.result) {
        setLoading(false);
        setNotFound(true);
        errorToastMessage(sRes.error, sRes.message);
        return;
      }
      const s = sRes.result;
      const samples = Array.isArray(s.samples) ? s.samples : [];
      setSession({
        samples,
        expert_prompt: s.expert_prompt,
        total: s.total ?? samples.length,
        // 배포 바인드 세션이면(=start 시 inference_playground_id 지정) VLM 샘플을 열람 시 실추론.
        inference_enabled: !!s.inference_enabled,
        // 생성 시스템 프롬프트(헤더 고정 박스, P3) — 러너 런/바인드 배포에서 옴(없으면 박스 숨김).
        gen_system_prompt: s.gen_system_prompt,
        // 세션 제목 — 생성 시 사용자가 입력해 동결한 값(없으면 헤더에 제목 줄 생략).
        run_name: s.run_name,
      });
      // 이전 채점 복원 — ratings[] 각 행(sample_idx 별 현재값)을 FE ratings 맵으로.
      const map = {};
      (Array.isArray(s.ratings) ? s.ratings : []).forEach((row) => {
        if (row == null || row.sample_idx == null) return;
        map[row.sample_idx] = {
          score: row.score,
          comment: row.comment || '',
          savedScore: row.score,
          savedComment: row.comment || '',
          rater: row.rater_user,
          ratedAt: row.create_datetime,
        };
      });
      setRatings(map);
      // 진행/집계 seed — getExpertResult 우선, 실패 시 ratings 수로 근사.
      if (rRes.status === STATUS_SUCCESS && rRes.result) {
        const p = rRes.result;
        setProgress({
          rated: p.rated ?? Object.keys(map).length,
          total: p.total ?? s.total ?? samples.length,
          avg_score: p.avg_score ?? 0,
          distribution: p.distribution ?? {},
          // getExpertResult 는 completed 필드 없이 status 만 준다 — 완료 세션 재개 시
          // 완료 배너/별점 비활성이 살아나도록 status 로 파생(samples status 로 폴백).
          completed: ((p && p.status) || (s && s.status)) === 'completed',
        });
      } else {
        setProgress({
          rated: Object.keys(map).length,
          total: s.total ?? samples.length,
          avg_score: 0,
          distribution: {},
          completed: false,
        });
      }
      setCurrent(0);
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [mId, jobId]);

  // 지연 단위 VLM 실추론 — 배포 바인드 세션에서 현재 샘플이 VLM(csv/이미지)이고 아직 mock 이면
  // 열람 시 배포 SDS 모델로 추론해 output 을 실출력으로 교체(영속·동결). 안 본 샘플은 GPU 미소모.
  // 실패/미바인드/비-VLM 은 no-op(mock 유지). BE 가 멱등·per-job 락이라 재열람/연타에도 안전.
  useEffect(() => {
    if (!session || !session.inference_enabled) return;
    const s = session.samples[current];
    if (!s || s.real_output) return;
    if (!(s.csv_rows || s.image_served)) return; // VLM 샘플만
    // 1회만 시도 — 실패(graceful mock)해도 재발화 금지. real_output 은 실패 시 false 로 남으므로
    // 그것만으로는 "미시도"와 "시도했으나 실패"를 구분 못 해 요청 폭주가 난다(리뷰 CRITICAL).
    if (attempted[s.idx]) return;
    const idx = s.idx;
    setAttempted((p) => ({ ...p, [idx]: true }));
    setInfering((p) => ({ ...p, [idx]: true }));
    (async () => {
      const res = await inferExpertSample(mId, jobId, idx);
      // 스피너 해제는 무조건(리뷰 HIGH: stuck flag 방지). 병합은 idx 기준이라 그 사이 다른
      // 샘플로 이동했어도 안전 — 완료된 실추론을 항상 반영(재방문 시 mock 잔존 방지).
      setInfering((p) => ({ ...p, [idx]: false }));
      // 실제 실출력이 생긴 경우만 병합 — graceful mock(real_output=false)은 session 갱신 불요
      // (불필요한 재렌더/effect 재발화 회피, 리뷰 CRITICAL).
      if (
        res.status === STATUS_SUCCESS &&
        res.result?.real_output &&
        res.result?.sample
      ) {
        const updated = res.result.sample;
        setSession((prev) =>
          prev
            ? {
                ...prev,
                samples: prev.samples.map((x) =>
                  x.idx === updated.idx ? { ...x, ...updated } : x,
                ),
              }
            : prev,
        );
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, session, jobId, mId]);

  const setComment = (idx, comment) =>
    setRatings((prev) => ({ ...prev, [idx]: { ...prev[idx], comment } }));

  // rate(idx, score) — 낙관적 반영 → 서버 영속 → 실패 시 롤백. 무변경(같은 score+코멘트)이면
  // 재제출 안 함(감사 이력 중복/rate_count 부풀림 방지). 정본=savedScore. (구 페이지 로직 동형.)
  const rate = async (idx, score) => {
    if (!session) return;
    const prev = ratings[idx] || {};
    const comment = prev.comment || '';
    if (prev.savedScore === score && (prev.savedComment || '') === comment) {
      return;
    }
    // 낮은 점수(≤COMMENT_REQUIRED_MAX_SCORE)는 코멘트가 있어야 확정한다. 코멘트 없이 별점만
    // 누른 상태는 화면에만 반영하고 서버 영속을 보류한다(‘다음’도 함께 잠긴다).
    //   ⚠️ 보류가 필수인 이유: 전량 채점되는 순간 BE 가 세션을 completed 로 마감하고, 완료
    //   세션은 재채점이 차단돼 코멘트를 덧붙일 수 없다. 즉 마지막 샘플을 별점만으로 확정하면
    //   그 샘플의 사유는 영영 남길 수 없다 — 확정 자체를 코멘트 뒤로 미뤄야 정책이 성립한다.
    if (score <= COMMENT_REQUIRED_MAX_SCORE && !comment.trim()) {
      setRatings((p) => ({ ...p, [idx]: { ...p[idx], score } }));
      return;
    }
    const prevScore = prev.score;
    setRatings((p) => ({ ...p, [idx]: { ...p[idx], score } }));
    const res = await submitExpertRating(mId, jobId, {
      sample_idx: idx,
      score,
      comment: comment || undefined,
    });
    if (res.status !== STATUS_SUCCESS) {
      setRatings((p) => ({ ...p, [idx]: { ...p[idx], score: prevScore } }));
      errorToastMessage(res.error, res.message);
      return;
    }
    setProgress(res.result);
    setRatings((p) => ({
      ...p,
      [idx]: {
        ...p[idx],
        score,
        rater: res.result?.rater_user,
        ratedAt: res.result?.rated_at,
        count: res.result?.rate_count,
        savedScore: score,
        savedComment: comment,
      },
    }));
  };

  if (loading) {
    return (
      <div className={cx('loading')}>
        <Loading />
        <span>{t('evaluation.project.loading')}</span>
      </div>
    );
  }
  if (notFound || !session) {
    return (
      <EmptyBox
        text='evaluation.failed'
        isBox
        isRed
        customStyle={{ height: '120px' }}
      />
    );
  }

  const samples = session.samples;
  const goPrev = () => setCurrent((c) => Math.max(0, c - 1));
  const goNext = () => setCurrent((c) => Math.min(samples.length - 1, c + 1));
  const sample = samples[current];
  const r = (sample && ratings[sample.idx]) || {};
  // 완료 세션은 읽기 전용이라 게이트를 걸지 않는다(과거 세션 열람이 막히면 안 됨).
  const commentRequired = !progress?.completed && needsComment(r);

  return (
    <div className={cx('expert')}>
      <div className={cx('review-head')}>
        <GenPromptBox prompt={session.gen_system_prompt} t={t} />
        <ExpertPromptBox prompt={session.expert_prompt} t={t} />
        <ExpertProgressHeader
          runName={session.run_name}
          rated={progress?.rated}
          total={progress?.total ?? session.total}
          current={current}
          count={samples.length}
          avgScore={progress?.avg_score}
          completed={progress?.completed}
          onPrev={goPrev}
          onNext={goNext}
          nextBlocked={commentRequired}
          onReset={onExit}
          t={t}
        />
      </div>

      {progress?.completed && (
        <ExpertCompletionBanner
          avgScore={progress?.avg_score}
          distribution={progress?.distribution}
          onReset={onExit}
          t={t}
        />
      )}

      {sample && (
        <div className={cx('review-body')} key={sample.idx}>
          <ContentBox>
            <div className={cx('review-content')}>
              <div className={cx('sample-badge')}>
                <Badge
                  label={`${sample.idx + 1} / ${samples.length}`}
                  type='blue'
                  size='lg'
                />
              </div>

              <ExpertSampleImage
                modelId={mId}
                jobId={jobId}
                sample={sample}
                t={t}
              />

              <CsvTable
                rows={sample.csv_rows}
                text={sample.csv_text}
                t={t}
              />

              {sample.input ? (
                <div className={cx('input-block')}>
                  <span className={cx('input-label')}>
                    {t('evaluation.expert.input')}
                  </span>
                  <div className={cx('input-text')}>{sample.input}</div>
                </div>
              ) : null}

              <div className={cx('output-block')}>
                <span className={cx('output-label')}>
                  {t('evaluation.expert.output')}
                </span>
                <div className={cx('output-text')}>
                  {infering[sample.idx]
                    ? t('evaluation.expert.inferring')
                    : sample.output}
                </div>
              </div>

              <div className={cx('rate-block')}>
                <StarRating
                  value={r.score}
                  onChange={(score) => rate(sample.idx, score)}
                  disabled={progress?.completed || !!infering[sample.idx]}
                  t={t}
                />
                <InputText
                  size='large'
                  placeholder={t(
                    commentRequired
                      ? 'evaluation.expert.commentPlaceholderRequired'
                      : 'evaluation.expert.commentPlaceholder',
                  )}
                  value={r.comment || ''}
                  onChange={(e) => setComment(sample.idx, e.target.value)}
                  onBlur={() => {
                    // 채점된 샘플의 코멘트 수정은 blur 시 영속(미완료 세션 한정, dedup 이 무변경 차단).
                    // 보류 중이던 낮은 점수도 코멘트가 채워진 이 시점에 함께 확정된다.
                    if (r.score && !progress?.completed)
                      rate(sample.idx, r.score);
                  }}
                  disableLeftIcon
                  disableClearBtn
                  customStyle={{ width: '100%' }}
                />
                {commentRequired && (
                  <span className={cx('comment-required')} role='alert'>
                    {t('evaluation.expert.commentRequired', {
                      score: COMMENT_REQUIRED_MAX_SCORE,
                    })}
                  </span>
                )}
              </div>

              {r.score && (r.rater || r.ratedAt) && (
                <div className={cx('audit-line')}>
                  {t('evaluation.expert.ratedBy', {
                    rater: r.rater || t('evaluation.expert.unknownRater'),
                  })}
                  {r.ratedAt ? ` · ${r.ratedAt}` : ''}
                  {r.count > 1
                    ? ` · ${t('evaluation.expert.reRated', {
                        count: r.count,
                      })}`
                    : ''}
                </div>
              )}
            </div>
          </ContentBox>
        </div>
      )}
    </div>
  );
};

export default ExpertRunView;
