import React, { useCallback, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import BorderTable from '@src/components/molecules/BorderTable';

import { deleteDataset, listDatasets } from '@src/apis/llm/dataset';
import { loadModalComponent } from '@src/modal';
import { STATUS_SUCCESS } from '@src/network';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { errorToastMessage } from '@src/utils';

import { Badge, Btn, PageHeader, SearchField, dsBase } from './components';
import { STATE_TONE } from './mock';
import { fmt } from './lib/format';
import common from './styles/common.module.scss';
import style from './pages.module.scss';

/**
 * 데이터셋 목록.
 *
 * 워크스페이스에 실제로 만들어진 파이프라인 데이터셋만 보여준다(`GET /datasets`).
 *
 * 통과율은 숫자만 보여주지 않고 정상 범위 위에 놓는다 — 82% 가 좋은 값인지 나쁜
 * 값인지는 범위를 봐야 알 수 있고, 상한을 넘으면 게이트가 헐거워 걸러지지 않는
 * 상태라 오히려 나쁜 신호다. 범위와 이탈 여부는 서버가 정본이라 그대로 받아 쓴다
 * (FE 가 임계값을 따로 들고 있으면 서버에서 기준을 바꿔도 화면이 옛 값을 계속 쓴다).
 */
export default function DatasetListPage() {
  const history = useHistory();
  const dispatch = useDispatch();
  const { id: wsId } = useParams();

  const [query, setQuery] = useState('');
  const [datasets, setDatasets] = useState([]);
  const [range, setRange] = useState(null);
  const [unreviewed, setUnreviewed] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await listDatasets(wsId);
    setLoading(false);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setDatasets(res.result?.datasets || []);
    setRange(res.result?.pass_rate_range || null);
    setUnreviewed(res.result?.unreviewed_total || 0);
  }, [wsId]);

  useEffect(() => {
    // 모달은 lazy 라 미리 받아 둔다 — 버튼을 누른 뒤 받으면 한 박자 비어 보인다.
    loadModalComponent('CREATE_DP_DATASET');
    load();
  }, [load]);

  const openCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_DP_DATASET',
        modalData: {
          workspace_id: wsId,
          // 만든 데이터셋이 목록에 바로 나타나야 만들어졌다는 것을 알 수 있다.
          handleRefresh: load,
        },
      }),
    );
  };

  const open = (d) => history.push(`${dsBase(wsId, d.id)}/flow`);

  // 무엇이 지워지고 무엇이 남는지를 확인 창에 적는다 — 작업 데이터셋이 함께 사라지는
  // 줄 알고 망설이거나, 반대로 남는 줄 모르고 스토리지를 찾아 헤매지 않게.
  // 실행 중이면 BE 가 이유와 함께 거절한다(잡 중지 경로가 없어 고아 파드를 막는다).
  const remove = (d) => {
    const work = d.work_dataset_name ? ` '${d.work_dataset_name}'` : '';
    dispatch(
      openConfirm({
        title: '파이프라인 삭제',
        content:
          `'${d.name}' 파이프라인을 삭제합니다. 노드 설정 · 실행 기록 · 심사 · 검수 결과가 함께 ` +
          '지워지고, 이 파이프라인이 띄운 모델 서빙은 내려갑니다.\n\n' +
          `작업 데이터셋${work}은 데이터 메뉴에 남습니다 — 릴리스한 학습셋을 쓰는 곳이 있을 수 ` +
          '있어 지우지 않습니다. 실행 중인 단계가 있으면 삭제되지 않습니다.',
        submit: {
          text: 'delete.label',
          func: async () => {
            const res = await deleteDataset(d.id);
            // 실패해도 목록은 다시 읽는다 — 모델 서빙을 내리느라 프록시 시간(60초)을 넘기면
            // 화면은 실패를 받지만 BE 는 삭제를 끝내므로, 안 읽으면 지워진 행이 남아 보인다.
            if (res.status !== STATUS_SUCCESS)
              errorToastMessage(res.error, res.message);
            load();
          },
        },
        cancel: { text: 'cancel.label' },
      }),
    );
  };

  const rows = query
    ? datasets.filter((d) =>
        (d.name || '').toLowerCase().includes(query.toLowerCase()),
      )
    : datasets;

  const columns = [
    {
      name: '데이터셋',
      selector: 'name',
      sortable: true,
      grow: 2,
      cell: (d) => (
        <span className={style['list-name']}>
          <span className={style['list-name-text']}>{d.name}</span>
          <span className={style['list-badges']}>
            <Badge tone={STATE_TONE[d.state_label] || 'gray'}>
              {d.state_label}
            </Badge>
            {!d.record_count && (
              <span className={style['list-hint']}>
                데이터 소스를 연결해 시작하세요
              </span>
            )}
          </span>
        </span>
      ),
    },
    {
      name: '레코드',
      selector: 'record_count',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={common['cell-num']}>
          {d.record_count ? fmt(d.record_count) : '—'}
        </span>
      ),
    },
    {
      // 범위는 서버가 준 값으로 쓴다. 아직 못 받았으면 범위 없이 제목만 둔다.
      name: range ? `통과율 ${range[0]}–${range[1]}%` : '통과율',
      selector: 'latest_pass_rate',
      sortable: true,
      cell: (d) => {
        if (d.latest_pass_rate === null || d.latest_pass_rate === undefined) {
          return <span className={common['cell-num']}>—</span>;
        }
        // 이탈 판정도 서버 값을 그대로 쓴다(pass_rate_flag).
        const out = d.pass_rate_flag === 'out_of_range';
        return (
          <span className={style['list-pass-row']}>
            <span
              className={[
                style['list-pass-value'],
                out ? style['list-pass-out'] : '',
              ].join(' ')}
            >
              {d.latest_pass_rate}%
            </span>
            {out && <Badge tone='fail'>범위 밖</Badge>}
          </span>
        );
      },
    },
    {
      name: '미검수',
      selector: 'unreviewed_count',
      sortable: true,
      right: true,
      cell: (d) => (
        <span
          className={[
            common['cell-num'],
            d.unreviewed_count ? common.warn : common.mute,
          ].join(' ')}
        >
          {/* 레코드가 아예 없으면 미검수라는 개념도 없다 — 다른 칸은 '—' 인데 여기만
              '0' 을 찍으면 같은 '데이터 없음' 을 두 방식으로 말하게 된다. */}
          {!d.record_count ? '—' : fmt(d.unreviewed_count || 0)}
        </span>
      ),
    },
    {
      name: '버전',
      selector: 'latest_version',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={[common['cell-num'], common.mute].join(' ')}>
          {d.latest_version || '—'}
        </span>
      ),
    },
    {
      name: '갱신',
      selector: 'update_datetime',
      sortable: true,
      right: true,
      cell: (d) => (
        <span className={[common['cell-num'], common.mute].join(' ')}>
          {/* 서버가 'YYYY-MM-DD HH:MM:SS' 로 포맷해 준다 — 목록엔 날짜만 쓴다. */}
          {(d.update_datetime || '').slice(0, 10) || '—'}
        </span>
      ),
    },
    {
      name: '',
      selector: 'open',
      sortable: false,
      right: true,
      cell: (d) => (
        <span className={style.toolbar}>
          <Btn size='sm' fill='outline' tone='gray' onClick={() => open(d)}>
            열기
          </Btn>
          <Btn size='sm' fill='outline' tone='danger' onClick={() => remove(d)}>
            삭제
          </Btn>
        </span>
      ),
    },
  ];

  return (
    <div className={style.page}>
      <PageHeader
        title='데이터셋'
        meta={`${datasets.length}개 데이터셋 · 미검수 합계 ${fmt(unreviewed)}건`}
        actions={
          <Btn size='md' onClick={openCreate}>
            ＋ 새 데이터셋
          </Btn>
        }
      />

      {/* 검색은 플랫폼 입력으로 표 위에 둔다 — 다른 LLM 화면의 표도 자체 검색 상자를
          끄고(hideSearchBox) 바깥에서 거르는 방식을 쓴다. */}
      <div className={common['row-between']}>
        <SearchField
          placeholder='데이터셋 이름으로 검색'
          value={query}
          onChange={setQuery}
        />
      </div>

      <BorderTable
        columns={columns}
        data={rows}
        loading={loading}
        selectableRows={false}
        hideSearchBox
        hideButtons
        onRowClick={(row) => open(row)}
      />
    </div>
  );
}
