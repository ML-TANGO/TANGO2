import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import EvalComparison from '../EvalComparison/EvalComparison';

import { getEvalCompare } from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalCrossCompare.module.scss';

const cx = classNames.bind(style);

const MAX_MODELS = 6; // llm_evaluation MAX_COMPARE_MODELS 와 일치(초과 시 BE 422 회피).

// 교차모델 비교 경량 뷰(④, §14.12). 여러 모델의 평가 이력을 한 표에 합쳐 메트릭별 best 를
//   전역(모델 무관)으로 표시. 런 생성 X — 읽기 전용 비교. 모델 다중선택은 ModelSelector(단일)
//   를 건드리지 않고 이 화면 전용 경량 칩 피커로 구현.
const EvalCrossCompare = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [selected, setSelected] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const reqRef = useRef(0); // 최신 비교 요청만 반영(빠른 토글 시 stale 응답 무시).
  const mountedRef = useRef(true); // 언마운트 후 도착 응답의 setState 차단.

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
  }, [dispatch]);

  // 언마운트 시 in-flight 비교 응답이 setState 하지 않도록 차단(codex).
  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  // 워크스페이스 학습완료 모델 목록(ModelSelector 와 동일 소스).
  useEffect(() => {
    if (!workspaceId) {
      setLoadingModels(false);
      return;
    }
    let cancelled = false;
    setLoadingModels(true);
    callApi({ url: `models?workspace_id=${workspaceId}`, method: 'GET' }).then(
      (res) => {
        if (cancelled) return;
        if (res.status === STATUS_SUCCESS) {
          const list = Array.isArray(res.result)
            ? res.result
            : res.result?.list ?? [];
          setModels(list.filter((m) => m.id != null));
        } else {
          errorToastMessage(res.error, res.message);
        }
        setLoadingModels(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const fetchCompare = useCallback(async (ids) => {
    if (!ids.length) {
      setComparison(null);
      return;
    }
    const reqId = ++reqRef.current;
    setLoadingCompare(true);
    try {
      const res = await getEvalCompare(ids);
      // 언마운트됐거나 더 최신 요청이 진행 중이면 무시(stale/post-unmount).
      if (!mountedRef.current || reqId !== reqRef.current) return;
      if (res.status === STATUS_SUCCESS) {
        setComparison(res.result);
      } else {
        errorToastMessage(res.error, res.message);
      }
    } finally {
      // 최신 요청만 스피너 해제 — stale 요청이 진행 중 스피너를 끄지 않도록(stuck 방지).
      if (mountedRef.current && reqId === reqRef.current) {
        setLoadingCompare(false);
      }
    }
  }, []);

  const toggle = (id) => {
    if (selected.includes(id)) {
      const next = selected.filter((x) => x !== id);
      setSelected(next);
      fetchCompare(next);
      return;
    }
    if (selected.length >= MAX_MODELS) {
      errorToastMessage(null, t('evaluation.compare.modelCap', { max: MAX_MODELS }));
      return;
    }
    const next = [...selected, id];
    setSelected(next);
    fetchCompare(next);
  };

  return (
    <div className={cx('cross-compare')}>
      <div className={cx('header')}>
        <button
          type='button'
          className={cx('back-btn')}
          onClick={() => history.push(`/user/workspace/${workspaceId}/evaluation`)}
        >
          ← {t('evaluation.backToHub')}
        </button>
        <h1 className={cx('title')}>{t('evaluation.compare.title')}</h1>
      </div>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.compare.selectModels')} ({selected.length}/{MAX_MODELS})
        </h3>
        {loadingModels ? (
          <p className={cx('empty')}>{t('evaluation.compare.loading')}</p>
        ) : models.length === 0 ? (
          <p className={cx('empty')}>{t('evaluation.compare.noModels')}</p>
        ) : (
          <div className={cx('chip-row')}>
            {models.map((m) => (
              <button
                key={m.id}
                type='button'
                className={cx('chip', selected.includes(m.id) && 'selected')}
                onClick={() => toggle(m.id)}
              >
                {m.name}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.compare.resultTitle')}</h3>
        {selected.length === 0 ? (
          <p className={cx('empty')}>{t('evaluation.compare.pickHint')}</p>
        ) : loadingCompare ? (
          <p className={cx('empty')}>{t('evaluation.compare.loading')}</p>
        ) : (
          <>
            <EvalComparison comparison={comparison} showModel />
            <div className={cx('hint')}>{t('evaluation.compare.hint')}</div>
          </>
        )}
      </section>
    </div>
  );
};

export default EvalCrossCompare;
