import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Selectbox } from '@jonathan/ui-react';

import MarkerBtn from '@src/components/atoms/MarkerBtn';

import { convertLocalTime } from '@src/datetimeUtils';
import { calcBeforeDateTime, convertBinaryByte } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserDatasetContent.module.scss';

const cx = classNames.bind(style);

// 업로드 지원 포맷 안내 칩(시각 안내용). CSV/TXT/Parquet → JSON/JSONL 변환은 전처리(빌트인)에서.
const FORMAT_TYPES = ['CSV', 'JSON', 'JSONL', 'Parquet', 'TXT', 'ZIP'];

const IS_MARKER = import.meta.env.VITE_REACT_APP_IS_MARKER === 'true';
const MARKER_VERSION = import.meta.env.VITE_REACT_APP_MARKER_VERSION;
const IS_DOWNLOAD =
  import.meta.env.VITE_REACT_APP_IS_DOWNLOAD_DATASET !== 'false';

// 데이터셋 관리(카드 그리드). ETRI LLMOps UI 디자인 채택 + 우리 실 데이터셋 API/핸들러 재배선.
//   기존 Table → 카드 리스트 + 업로드 존(드래그&드롭) + 포맷 안내 + 다중선택 삭제.
//   ⚠️ ETRI 의 변환(Transformation) 모달은 제외 — 데이터 변환은 fb_preprocessing 빌트인 전처리로 분리.
function UserDatasetContent({
  tableData = [],
  totalRows,
  keyword,
  onCreate,
  onSearch,
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

  const [isDragging, setIsDragging] = useState(false);
  const [localSelected, setLocalSelected] = useState(new Set());

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

  // 카드 선택은 로컬 Set 으로 관리하되, 삭제는 부모 selectedRows 를 쓰므로 매 토글마다 동기화.
  const toggleSelect = (item) => {
    const next = new Set(localSelected);
    if (next.has(item.id)) next.delete(item.id);
    else next.add(item.id);
    setLocalSelected(next);
    onSelect?.({ selectedRows: tableData.filter((d) => next.has(d.id)) });
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };
  // 드롭 = 업로드 모달 오픈(파일 처리는 기존 생성 모달이 담당, ETRI 동일).
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    onCreate();
  };

  return (
    <div id='UserDatasetContent' className={cx('wrapper')}>
      {/* 헤더 */}
      <div className={cx('page-header')}>
        <div className={cx('title-box')}>
          <h1 className={cx('title')}>{t('datasetManagement.label')}</h1>
          <p className={cx('title-sub')}>{t('dataset.subtitle')}</p>
        </div>
        <div className={cx('header-actions')}>
          <button
            className={cx('outline-btn')}
            onClick={() => onClickDataResourceSetting?.()}
            disabled
          >
            {t('dataResourceManagementSettings.label')}
          </button>
          <button className={cx('primary-btn')} onClick={() => onCreate()}>
            {t('createDataset.label')}
          </button>
        </div>
      </div>

      {/* 업로드 존 */}
      <div
        className={cx('upload-zone', isDragging && 'dragging')}
        role='button'
        tabIndex={0}
        onClick={() => onCreate()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onCreate();
          }
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className={cx('upload-icon')}>📂</div>
        <div className={cx('upload-title')}>{t('dataset.upload.title')}</div>
        <div className={cx('upload-desc')}>{t('dataset.upload.desc')}</div>
        <div className={cx('fmt-row')}>
          {FORMAT_TYPES.map((fmt) => (
            <span key={fmt} className={cx('fmt-chip')}>
              {fmt}
            </span>
          ))}
        </div>
      </div>

      {/* 목록 */}
      <div className={cx('section')}>
        <div className={cx('section-header')}>
          <span className={cx('section-title')}>{t('dataset.list.title')}</span>
          <span className={cx('count-badge')}>
            {t('dataset.count', { count: totalRows ?? 0 })}
          </span>
          <div className={cx('spacer')} />
          {localSelected.size > 0 && (
            <button className={cx('delete-btn')} onClick={openDeleteConfirmPopup}>
              {t('delete.label')} ({localSelected.size})
            </button>
          )}
        </div>

        {/* 툴바 */}
        <div className={cx('list-toolbar')}>
          <div className={cx('search-wrap')}>
            <input
              className={cx('search-input')}
              placeholder={t('dataset.search.placeholder')}
              value={keyword}
              onChange={(e) => onSearch(e.target.value)}
            />
            {keyword && (
              <button className={cx('search-clear')} onClick={onClear}>
                ✕
              </button>
            )}
          </div>
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
        </div>

        {/* 카드 리스트 */}
        {tableData.length === 0 ? (
          <div className={cx('empty-inline')}>{t('dataset.empty')}</div>
        ) : (
          <div className={cx('ds-list')}>
            {tableData.map((item) => {
              const sel = localSelected.has(item.id);
              const canEdit = item.permission_level < 4;
              const isRO = Number(item.access) === 0;
              const isDown = downloading && downloadIds.includes(item.id);
              const canDownload = item.file_count > 0 && IS_DOWNLOAD;
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
                        className={cx('icon-action-btn')}
                        onClick={() => onEditRow(item)}
                      >
                        {t('edit.label')}
                      </button>
                    )}
                    {onDownloadRow && (
                      <button
                        className={cx(
                          'icon-action-btn',
                          (!canDownload || isDown) && 'icon-action-btn--disabled',
                        )}
                        disabled={!canDownload || isDown}
                        onClick={() =>
                          canDownload &&
                          !isDown &&
                          onDownloadRow(item.id, item.dataset_name)
                        }
                      >
                        {isDown
                          ? t('dataset.downloading')
                          : t('download.label')}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default UserDatasetContent;
