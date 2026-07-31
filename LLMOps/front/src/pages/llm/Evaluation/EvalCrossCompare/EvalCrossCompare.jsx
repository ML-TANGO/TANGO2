import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import { Badge, Checkbox, Loading } from '@jonathan/ui-react';

import EvalComparison from '../EvalComparison/EvalComparison';

import EmptyBox from '@src/components/molecules/EmptyBox';
import GuideBox from '@src/components/molecules/GuideBox';

import { getEvalCompare } from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalCrossCompare.module.scss';

const cx = classNames.bind(style);

const MAX_MODELS = 6; // llm_evaluation MAX_COMPARE_MODELS 와 일치(초과 시 BE 422 회피).

// 교차모델 비교 경량 뷰(④, §14.12). 여러 모델의 평가 이력을 한 표에 합쳐 메트릭별 best 를
//   전역(모델 무관)으로 표시. 런 생성 X — 읽기 전용 비교. 모델 다중선택은 이 화면 전용
//   Checkbox 목록으로 제공한다.
const EvalCrossCompare = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
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
      errorToastMessage(
        null,
        t('evaluation.compare.modelCap', { max: MAX_MODELS }),
      );
      return;
    }
    const next = [...selected, id];
    setSelected(next);
    fetchCompare(next);
  };

  return (
    <div className={cx('cross-compare')}>
      <section className={cx('section')}>
        <div className={cx('section-head')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.compare.selectModels')}
          </h3>
          <Badge
            label={`${selected.length}/${MAX_MODELS}`}
            type='blue'
            size='sm'
          />
        </div>
        {loadingModels ? (
          <div className={cx('loading-state')}>
            <Loading />
            <span>{t('evaluation.compare.loading')}</span>
          </div>
        ) : models.length === 0 ? (
          <EmptyBox
            text='evaluation.compare.noModels'
            isBox
            customStyle={{ height: '120px' }}
          />
        ) : (
          <>
            <div className={cx('model-options')}>
              {models.map((m) => {
                const checked = selected.includes(m.id);
                return (
                  <div
                    key={m.id}
                    className={cx('model-option', checked && 'selected')}
                  >
                    <Checkbox
                      checked={checked}
                      onChange={() => toggle(m.id)}
                      label={m.name}
                      customLabelStyle={{ width: '100%' }}
                    />
                  </div>
                );
              })}
            </div>
            <div className={cx('guide')}>
              <GuideBox
                title={t('evaluation.compare.modelCap', {
                  max: MAX_MODELS,
                })}
                isTitleIcon
                textList={[]}
              />
            </div>
          </>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.compare.resultTitle')}
        </h3>
        {selected.length === 0 ? (
          <EmptyBox
            text='evaluation.compare.pickHint'
            isBox
            customStyle={{ height: '120px' }}
          />
        ) : loadingCompare ? (
          <div className={cx('loading-state')}>
            <Loading />
            <span>{t('evaluation.compare.loading')}</span>
          </div>
        ) : (
          <>
            <EvalComparison comparison={comparison} showModel />
            <div className={cx('guide')}>
              <GuideBox
                title={t('evaluation.compare.hint')}
                isTitleIcon
                textList={[]}
              />
            </div>
          </>
        )}
      </section>
    </div>
  );
};

export default EvalCrossCompare;
