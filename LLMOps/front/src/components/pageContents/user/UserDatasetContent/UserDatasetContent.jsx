import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2, InputText, Selectbox } from '@jonathan/ui-react';

import MarkerBtn from '@src/components/atoms/MarkerBtn';
import PageTitle from '@src/components/atoms/PageTitle';

import { convertLocalTime } from '@src/datetimeUtils';
import { calcBeforeDateTime, convertBinaryByte } from '@src/utils';
import { callApi, STATUS_SUCCESS } from '@src/network';

import editIcon from '@src/static/images/icon/00-ic-basic-pen.svg';
import downloadIcon from '@src/static/images/icon/00-ic-data-download.svg';
import loadingIcon from '@src/static/images/icon/spinner-1s-58.svg';

import classNames from 'classnames/bind';
import style from './UserDatasetContent.module.scss';

const cx = classNames.bind(style);

const IS_MARKER = import.meta.env.VITE_REACT_APP_IS_MARKER === 'true';
const MARKER_VERSION = import.meta.env.VITE_REACT_APP_MARKER_VERSION;
const IS_DOWNLOAD =
  import.meta.env.VITE_REACT_APP_IS_DOWNLOAD_DATASET !== 'false';

// 데이터셋 관리(카드 그리드). 카드 리스트 + 다중선택 삭제 + 카드별 파일 미리보기.
//   업로드/드래그앤드롭/폴더생성은 상세 진입 후에만(생성 화면은 목록+생성만).

// 카드별 파일 미리보기 — 목록 API 엔 파일명이 없어 데이터셋마다 상위 4개를 지연 조회.
//   (빈 데이터셋/조회 실패는 조용히 빈 상태로 처리)
function DatasetFilePreview({ datasetId, t, onLoaded }) {
  // 목록 API 는 file_count 를 주지 않으므로 항상 파일을 조회해 결과로 빈 여부를 판단.
  const [state, setState] = useState(null); // null=로딩 / { files, total }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await callApi({
        // 상세 페이지 조회와 동일 파라미터 — search_type=all 이라야 dir+file 이 나오고
        // (미지정 시 file 만/또는 필수 파라미터 누락), search_value/key 는 빈 값(필터 없음).
        url: `datasets/${datasetId}/files?search_page=1&search_size=4&search_type=all&search_value=&search_key=`,
        method: 'GET',
      });
      if (cancelled) return;
      if (res?.status === STATUS_SUCCESS) {
        const list = res.result?.list ?? [];
        const total = res.result?.file_count ?? list.length;
        setState({ files: list, total });
        onLoaded?.(total);
      } else {
        setState({ files: [], total: 0 });
        onLoaded?.(0);
      }
    })();
    return () => {
      cancelled = true;
    };
    // onLoaded 는 매 렌더 새 함수라 deps 에서 제외(재조회 방지)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  if (state === null) {
    return <div className={cx('ds-preview', 'ds-preview--empty')}>· · ·</div>;
  }
  if (state.files.length === 0) {
    return (
      <div className={cx('ds-preview', 'ds-preview--empty')}>
        {t('emptyFile.label', '파일 없음')}
      </div>
    );
  }
  return (
    <ul className={cx('ds-preview')}>
      {state.files.slice(0, 4).map((f) => (
        <li key={f.name} className={cx('ds-preview-item')} title={f.name}>
          {f.name}
        </li>
      ))}
      {state.total > 4 && (
        <li className={cx('ds-preview-more')}>+{state.total - 4}</li>
      )}
    </ul>
  );
}

function UserDatasetContent({
  tableData = [],
  totalRows,
  keyword,
  searchKey,
  onCreate,
  onSearch,
  onSearchKeyChange,
  onClear,
  accessType,
  onAccessTypeChange,
  onRowClick,
  onSelect,
  toggledClearRows,
  openDeleteConfirmPopup,
  onClickDataResourceSetting,
  onEditRow,
  onDownloadRow,
  downloading,
  downloadIds = [],
}) {
  const { t } = useTranslation();

  const [localSelected, setLocalSelected] = useState(new Set());
  // 카드별 실제 파일수(미리보기 조회 결과) — 목록 API 가 file_count 를 안 줘서 다운로드 활성 판정에 사용.
  const [fileTotals, setFileTotals] = useState({});

  // 부모의 toggledClearRows 토글 시 선택 초기화(삭제 후 등).
  useEffect(() => {
    setLocalSelected(new Set());
  }, [toggledClearRows]);

  // 검색/필터로 tableData 가 줄면 숨겨진 선택 항목 정리 + 부모 selectedRows 재동기 —
  // 보이지 않는 항목이 selectedRows 에 남아 삭제되는 것 방지(리뷰 H1). 토글은 이미 동기라
  // tableData 축소 시에만 prune 필요 → localSelected 는 의도적으로 deps 제외.
  useEffect(() => {
    const visibleSel = tableData.filter((d) => localSelected.has(d.id));
    if (visibleSel.length !== localSelected.size) {
      setLocalSelected(new Set(visibleSel.map((d) => d.id)));
      onSelect?.({ selectedRows: visibleSel });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableData]);

  // 수정 시각(상대) — calcBeforeDateTime 은 {unit, beforeTime} 객체를 반환하므로
  // 그대로 렌더하면 React 크래시. 부모 Table 컬럼과 동일하게 i18n 으로 포맷(리뷰).
  const formatEdited = (diffTimeEdit) => {
    if (!diffTimeEdit) return '-';
    const r = calcBeforeDateTime(diffTimeEdit);
    return t(`before.${r.unit}.label`, { [r.unit]: r.beforeTime });
  };

  const accessTypeOptions = [
    { label: 'allAccessType.label', value: 'all' },
    { label: 'readAndWrite.label', value: 1 },
    { label: 'readOnly.label', value: 0 },
  ];

  const searchOptions = [
    { label: 'datasetName.label', value: 'dataset_name' },
    { label: 'creator.label', value: 'owner' },
  ];

  // 최신순 정렬 — id 는 자동증가 PK 라 생성 순서와 일치(최신→오래된).
  const sortedData = [...tableData].sort((a, b) => b.id - a.id);

  // 카드 선택은 로컬 Set 으로 관리하되, 삭제는 부모 selectedRows 를 쓰므로 매 토글마다 동기화.
  const toggleSelect = (item) => {
    const next = new Set(localSelected);
    if (next.has(item.id)) next.delete(item.id);
    else next.add(item.id);
    setLocalSelected(next);
    onSelect?.({ selectedRows: tableData.filter((d) => next.has(d.id)) });
  };

  return (
    <div id='UserDatasetContent' className={cx('wrapper')}>
      {/* 헤더 */}
      <div className={cx('page-header')}>
        <PageTitle>{t('datasetManagement.label')}</PageTitle>
        <div className={cx('header-actions')}>
          <ButtonV2
            colorType='skyblue'
            size='m'
            label={t('dataResourceManagementSettings.label')}
            disabled
            onClick={() => onClickDataResourceSetting?.()}
          />
          <ButtonV2
            colorType='blue'
            size='m'
            label={t('createDataset.label')}
            onClick={() => onCreate()}
          />
        </div>
      </div>

      {/* 목록 */}
      <div className={cx('section')}>
        {/* 툴바 — 우측정렬: 접근권한 > 검색키 > 검색입력 (기존 조나단 순서) */}
        <div className={cx('list-toolbar')}>
          <div className={cx('btn-filter')}>
            <Selectbox
              size='medium'
              list={accessTypeOptions}
              selectedItem={accessType}
              customStyle={{
                selectboxForm: { width: '160px' },
                listForm: { width: '160px' },
              }}
              onChange={onAccessTypeChange}
              t={t}
            />
          </div>
          <div className={cx('btn-filter')}>
            <Selectbox
              size='medium'
              list={searchOptions}
              selectedItem={searchKey}
              customStyle={{
                selectboxForm: { width: '150px' },
                listForm: { width: '150px' },
              }}
              onChange={onSearchKeyChange}
              t={t}
            />
          </div>
          <div className={cx('search-wrap')}>
            <InputText
              value={keyword}
              type='medium'
              placeholder={t('dataset.search.placeholder')}
              leftIcon='/images/icon/ic-search.svg'
              closeIcon='/images/icon/close-c.svg'
              onChange={(e) => onSearch(e?.target.value)}
              onClear={onClear}
              disableLeftIcon={false}
              disableClearBtn={false}
              customStyle={{ width: '220px' }}
            />
          </div>
        </div>

        {/* 카드 리스트 */}
        {tableData.length === 0 ? (
          <div className={cx('empty-inline')}>{t('dataset.empty')}</div>
        ) : (
          <div className={cx('ds-list')}>
            {sortedData.map((item) => {
              const sel = localSelected.has(item.id);
              const canEdit = item.permission_level < 4;
              const isRO = Number(item.access) === 0;
              const isDown = downloading && downloadIds.includes(item.id);
              const fileTotal = fileTotals[item.id] ?? 0;
              const canDownload = fileTotal > 0 && IS_DOWNLOAD;
              return (
                <div
                  key={item.id}
                  className={cx('ds-card', sel && 'ds-card--on')}
                  role='button'
                  tabIndex={0}
                  onClick={() => onRowClick(item)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onRowClick(item);
                  }}
                >
                  <div
                    className={cx('ds-check', sel && 'ds-check--on')}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleSelect(item);
                    }}
                  >
                    {sel && '✓'}
                  </div>
                  <div className={cx('ds-card-body')}>
                    <div className={cx('ds-card-name-row')}>
                      <span className={cx('ds-card-name')}>
                        {item.dataset_name}
                      </span>
                      <span
                        className={cx(
                          'ds-access-badge',
                          isRO ? 'ds-access--ro' : 'ds-access--rw',
                        )}
                      >
                        {isRO ? t('readOnly.label') : t('readAndWrite.label')}
                      </span>
                    </div>
                    <div className={cx('ds-card-meta')}>
                      <span>{item.owner || '-'}</span>
                      <span className={cx('dot')}>·</span>
                      <span>
                        {item.size ? convertBinaryByte(item.size) : '0 Bytes'}
                      </span>
                      <span className={cx('dot')}>·</span>
                      <span>{formatEdited(item.diffTimeEdit)}</span>
                      <span className={cx('dot')}>·</span>
                      <span>
                        {item.create_datetime
                          ? convertLocalTime(item.create_datetime)
                          : '-'}
                      </span>
                    </div>
                    <DatasetFilePreview
                      datasetId={item.id}
                      t={t}
                      onLoaded={(n) =>
                        setFileTotals((prev) =>
                          prev[item.id] === n
                            ? prev
                            : { ...prev, [item.id]: n },
                        )
                      }
                    />
                  </div>
                  <div
                    className={cx('ds-card-actions')}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {IS_MARKER && MARKER_VERSION === '1' && (
                      <MarkerBtn
                        workspaceName={item.workspace_name}
                        datasetId={item.id}
                        datasetName={item.dataset_name}
                        disabled={item.file_count === 0}
                      />
                    )}
                    {onEditRow && canEdit && (
                      <button
                        type='button'
                        className={cx('icon-btn')}
                        title={t('edit.label')}
                        onClick={() => onEditRow(item)}
                      >
                        <img src={editIcon} alt={t('edit.label')} />
                      </button>
                    )}
                    {onDownloadRow && (
                      <button
                        type='button'
                        className={cx(
                          'icon-btn',
                          (!canDownload || isDown) && 'icon-btn--disabled',
                        )}
                        title={t('download.label')}
                        disabled={!canDownload || isDown}
                        onClick={() =>
                          canDownload &&
                          !isDown &&
                          onDownloadRow(item.id, item.dataset_name)
                        }
                      >
                        <img
                          src={isDown ? loadingIcon : downloadIcon}
                          alt={t('download.label')}
                          className={cx(isDown && 'spin')}
                        />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 하단 좌측: 선택 데이터셋 삭제 */}
        <div className={cx('list-footer')}>
          <button
            type='button'
            className={cx('delete-btn')}
            onClick={openDeleteConfirmPopup}
            disabled={localSelected.size === 0}
          >
            {t('delete.label')}
            {localSelected.size > 0 ? ` (${localSelected.size})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
}

export default UserDatasetContent;
