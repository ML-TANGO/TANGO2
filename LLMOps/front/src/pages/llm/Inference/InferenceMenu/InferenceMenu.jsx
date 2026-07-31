import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import Card from '@src/components/molecules/CardTemplate/Card';
import CardList from '@src/components/molecules/CardTemplate/CardList';
import EmptyBox from '@src/components/molecules/EmptyBox';
import { getPlayground } from '@src/apis/llm/playground';
import useIntervalCall from '@src/hooks/useIntervalCall';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './InferenceMenu.module.scss';

const cx = classNames.bind(style);

// 카드 크기 — 배포 목록(CardTemplate 기본값)과 동일하게 맞춘다.
const CARD_HEIGHT = 340;

// 추론(Inference) 랜딩 — consume 레이어(목록·상세만, 생성 진입점 없음).
//   카드는 배포 목록(PlaygroundMenu)과 같은 플랫폼 Card/CardList 를 그대로 재사용 → 두 탭 룩 일치.
//   상태 배지/유형 칩도 Card 내장(statusBadge·typeBadge)을 쓰므로 화면 자체 배지 스타일은 두지 않는다.
//   이중모델 세션(mode==='dual', WBS 4.2/4.3)은 전 상태 노출(생성 직후 준비중 추적),
//   단일 배포는 running 만 노출(질의 가능). 세션 생성은 배포 탭(NewDeploymentModal)에서.
//   자식(프롬프트생성) playground 는 BE(get_playground_list)가 목록에서 숨김.
const InferenceMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const history = useHistory();
  const { id: workspaceId } = match.params;

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = useCallback(async () => {
    const res = await getPlayground(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      const list = Array.isArray(res.result) ? res.result : [];
      // 추론 메뉴는 '질의 가능한 배포'만 나열한다 — 이중도 단일과 같은 기준(running).
      //   종전엔 이중만 전 상태를 노출해 준비중을 추적했으나, 질의할 수 없는 세션이 목록을
      //   채우는 문제가 있어 구성/배포 추적은 배포 탭 소관으로 넘긴다.
      //   이중 부모의 status 는 집계값이라 LLM1·LLM2 가 모두 running 일 때만 running 이다.
      const visible = list.filter((d) => d.status === 'running');
      // 카드 표시용으로만 변환(원본 불변) — 배포 목록의 매핑 규약과 동일한 필드 이름 사용.
      setSessions(
        visible.map((d) => {
          const isDual = d.mode === 'dual';
          const promptName = d.prompt_gen_model_name;
          const inferName = d.inference_model_name;
          return {
            id: d.id,
            title: d.name,
            // 이중은 어떤 모델 쌍인지가 핵심 정보 → 설명 자리에 모델 쌍을 노출.
            subTitle:
              isDual && (promptName || inferName)
                ? `프롬프트 ${promptName ?? '-'} → 추론 ${inferName ?? '-'}`
                : d.description,
            constructor: d.owner,
            createTime: d.create_datetime,
            updateTime: d.update_datetime,
            isAccess: d.access,
            status: d.status,
            // 이중은 항상 cluster 라 유형 칩이 중복 정보다. 상태+유형+이중 3칩이 카드 너비를
            //   넘겨 줄바꿈되므로 이중 행에서는 유형 칩을 생략하고 qualifier 만 남긴다.
            //   단일은 종전대로 '단일 모델' 칩 하나를 유지한다.
            typeBadge: isDual ? undefined : '단일 모델',
            typeBadgeKind: isDual ? undefined : 'single',
            qualifierBadge: isDual ? '이중모델' : undefined,
            qualifierBadgeKind: isDual ? 'multimodal' : undefined,
          };
        }),
      );
      setLoading(false);
      return;
    }
    errorToastMessage(res.error, res.message);
    setLoading(false);
  }, [workspaceId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Inference' } }]));
    fetchSessions();
  }, [dispatch, fetchSessions]);

  // 준비 중(installing) 세션이 실행 중으로 바뀌는 것을 자동 반영 — 5s 폴링(탭 비활성 시 자동 정지).
  const pollSessions = useCallback(async () => {
    await fetchSessions();
    return true;
  }, [fetchSessions]);

  useIntervalCall(pollSessions, 5000);

  // Card 의 onClick 규약: (e, id, constructor, isAccess, userList)
  const openInference = useCallback(
    (e, id) => {
      history.push(`/user/workspace/${workspaceId}/inference/${Number(id)}`);
    },
    [history, workspaceId],
  );

  return (
    <div className={cx('inference-cont')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>{t('Inference')}</h1>
        <span className={cx('sub')}>
          생성된 배포(단일·이중모델)로 추론을 수행합니다. 새 배포는 배포 탭에서
          생성합니다.
        </span>
      </div>

      {loading ? null : sessions.length === 0 ? (
        <EmptyBox
          isBox
          customStyle={{ height: '220px' }}
          text='추론할 배포가 없습니다. 배포 탭에서 단일·이중모델 배포를 생성하세요.'
        />
      ) : (
        <CardList>
          {sessions.map((s) => (
            <Card
              key={s.id}
              id={s.id}
              title={s.title}
              subTitle={s.subTitle}
              constructor={s.constructor}
              createTime={s.createTime}
              updateTime={s.updateTime}
              isAccess={s.isAccess}
              status={s.status}
              statusBadge
              typeBadge={s.typeBadge}
              typeBadgeKind={s.typeBadgeKind}
              qualifierBadge={s.qualifierBadge}
              qualifierBadgeKind={s.qualifierBadgeKind}
              handleOnClickCard={openInference}
              height={CARD_HEIGHT}
            />
          ))}
        </CardList>
      )}
    </div>
  );
};

export default InferenceMenu;
