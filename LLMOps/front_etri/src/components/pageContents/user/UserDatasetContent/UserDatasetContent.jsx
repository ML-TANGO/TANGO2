import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Selectbox } from '@tango/ui-react';

import DatasetCheckModalContainer from '@src/components/Modal/DatasetCheckModal/DatasetCheckModalContainer';
import Table from '@src/components/molecules/Table';
import { toast } from '@src/components/Toast';
import { convertBinaryByte, numberWithCommas } from '@src/utils';
import { convertLocalTime } from '@src/datetimeUtils';

import classNames from 'classnames/bind';
import style from './UserDatasetContent.module.scss';
import closeIcon from '@src/static/images/icon/00-ic-black-close.svg';

const cx = classNames.bind(style);

const FORMAT_TYPES = ['CSV', 'JSON', 'JSONL', 'Parquet', 'TXT', 'ZIP'];

function UserDatasetContent({
  columns,
  tableData,
  totalRows,
  keyword,
  searchKey,
  onCreate,
  openDeleteConfirmPopup,
  onSearchKeyChange,
  onSearch,
  onSelect,
  onRowClick,
  deleteBtnDisabled,
  toggledClearRows,
  accessType,
  onAccessTypeChange,
  onAllSync,
  loading,
  onClear,
  builtInModalOpen,
  builtInModalOpenHandler,
  builtInModelList,
  builtInTemplateOpen,
  onClickDataResourceSetting,
  onSortHandler,
  transformColumns,
  transformations = [],
  isTransformModalOpen,
  selectedTransformItem,
  onOpenTransformModal,
  onCloseTransformModal,
  onTransformRowClick,
  datasets = [],
}) {
  const { t } = useTranslation();

  const [isDragging, setIsDragging]     = useState(false);
  const [isTransforming, setIsTransforming] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [outputFormats, setOutputFormats] = useState({
    JSON: true, CSV: false, Parquet: false, JSONL: false,
  });

  const datasetOptions = datasets.map((item) => ({
    label: item.dataset_name,
    value: item.id,
  }));

  useEffect(() => {
    if (isTransformModalOpen) {
      setOutputFormats({ JSON: true, CSV: false, Parquet: false, JSONL: false });
      if (datasets.length > 0) {
        const opts = datasets.map((d) => ({ label: d.dataset_name, value: d.id }));
        setSelectedDataset(opts.find((o) => o.label === 'SDS Dataset') || opts[0]);
      } else {
        setSelectedDataset(null);
      }
    }
  }, [isTransformModalOpen, datasets]);

  const handleFormatChange = (fmt) =>
    setOutputFormats((prev) => ({ ...prev, [fmt]: !prev[fmt] }));

  const isAnyFormatSelected = Object.values(outputFormats).some(Boolean);

  const handleStartTransformation = () => {
    setIsTransforming(true);
    setTimeout(() => {
      setIsTransforming(false);
      toast.success('Transformation completed');
      onCloseTransformModal();
    }, 1500);
  };

  const handleDragOver  = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop      = (e) => { e.preventDefault(); setIsDragging(false); onCreate(); };

  const accessTypeOptions = [
    { label: 'allAccessType.label', value: 'all' },
    { label: 'readAndWrite.label',  value: 1 },
    { label: 'readOnly.label',      value: 0 },
  ];

  const searchOptions = [
    { label: 'datasetName.label', value: 'dataset_name' },
    { label: 'creator.label',     value: 'owner' },
  ];

  const filterList = (
    <div className={cx('btn-filter')}>
      <Selectbox
        size='medium'
        list={accessTypeOptions}
        selectedItem={accessType}
        customStyle={{ selectboxForm: { width: '160px' }, listForm: { width: '160px' } }}
        onChange={onAccessTypeChange}
        t={t}
      />
    </div>
  );

  const topButtonList = (
    <div className={cx('modal-wrap')}>
      {builtInModalOpen && (
        <DatasetCheckModalContainer
          list={builtInModelList}
          closeFunc={builtInModalOpenHandler}
          submit={{ func: builtInTemplateOpen, text: t('openTemplate.label') }}
        />
      )}
    </div>
  );

  const bottomButtonList = (
    <button
      className={cx('delete-btn', deleteBtnDisabled && 'disabled')}
      onClick={openDeleteConfirmPopup}
      disabled={deleteBtnDisabled}
    >
      {t('delete.label')}
    </button>
  );

  return (
    <div className={cx('wrapper')}>

      {/* ── 페이지 헤더 ── */}
      <div className={cx('page-header')}>
        <div className={cx('title-box')}>
          <h1 className={cx('title')}>데이터셋 관리</h1>
          <p className={cx('title-sub')}>로컬 데이터를 업로드하고 학습 데이터셋으로 변환·관리합니다</p>
        </div>
        <div className={cx('header-actions')}>
          <button className={cx('outline-btn')} onClick={onClickDataResourceSetting} disabled>
            리소스 설정
          </button>
          <button className={cx('primary-btn')} onClick={onCreate}>
            + 데이터셋 추가
          </button>
        </div>
      </div>

      {/* ── 업로드 존 ── */}
      <div
        className={cx('upload-zone', isDragging && 'dragging')}
        onClick={onCreate}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className={cx('upload-icon')}>📂</div>
        <div className={cx('upload-title')}>로컬 데이터셋 업로드</div>
        <div className={cx('upload-desc')}>파일을 이 영역으로 드래그하거나 클릭하여 업로드하세요</div>
        <div className={cx('fmt-row')}>
          {FORMAT_TYPES.map((fmt) => (
            <span key={fmt} className={cx('fmt-chip')}>{fmt}</span>
          ))}
        </div>
      </div>

      {/* ── 데이터셋 목록 ── */}
      <div className={cx('section')}>
        <div className={cx('section-header')}>
          <span className={cx('section-title')}>데이터셋 목록</span>
          <span className={cx('count-badge')}>{totalRows}개</span>
          <div className={cx('spacer')} />
        </div>
        <div className={cx('table-wrap')}>
          <Table
            columns={columns}
            data={tableData}
            totalRows={totalRows}
            topButtonList={topButtonList}
            bottomButtonList={tableData.length > 0 && bottomButtonList}
            onRowClick={onRowClick}
            onSelect={onSelect}
            defaultSortField='create_datetime'
            toggledClearRows={toggledClearRows}
            filterList={filterList}
            selectableRowDisabled={({ permission_level: pl }) => pl > 3}
            searchOptions={searchOptions}
            searchKey={searchKey}
            keyword={keyword}
            onSearchKeyChange={onSearchKeyChange}
            onSearch={(e) => onSearch(e.target.value)}
            onClear={onClear}
            onSortHandler={onSortHandler}
          />
        </div>
      </div>

      {/* ── 학습 데이터셋 변환 ── */}
      <div className={cx('section')}>
        <div className={cx('section-header')}>
          <span className={cx('section-title')}>학습 데이터셋 변환</span>
          <span className={cx('section-desc')}>원시 데이터를 학습용 포맷으로 변환합니다</span>
          <div className={cx('spacer')} />
          <button
            className={cx('primary-btn')}
            onClick={() => transformations.length > 0 && onOpenTransformModal(transformations[0])}
          >
            + 새 변환 생성
          </button>
        </div>

        {transformations.length === 0 ? (
          <div className={cx('empty-state')}>
            <span className={cx('empty-icon')}>⚗️</span>
            <p className={cx('empty-title')}>변환된 데이터셋이 없습니다</p>
            <p className={cx('empty-desc')}>데이터셋을 선택하여 학습용 포맷으로 변환해 보세요</p>
            <button className={cx('primary-btn')} onClick={() => onOpenTransformModal && onOpenTransformModal(null)}>
              + 변환 시작하기
            </button>
          </div>
        ) : (
          <div className={cx('transform-grid')}>
            {transformations.map((item) => (
              <div
                key={item.id}
                className={cx('transform-card')}
                onClick={() => onTransformRowClick(item)}
              >
                <div className={cx('tc-head')}>
                  <span className={cx('tc-name')}>{item.dataset_name}</span>
                  <span className={cx('tc-badge')}>학습 데이터셋</span>
                </div>
                <div className={cx('tc-arrow-row')}>
                  <span className={cx('tc-source')}>{item.source_dataset_name || '원본 데이터셋'}</span>
                  <span className={cx('tc-arrow')}>→</span>
                  <span className={cx('tc-target')}>{item.dataset_name}</span>
                </div>
                <div className={cx('tc-meta')}>
                  <span>{item.file_count ? `${numberWithCommas(item.file_count)}개 파일` : '-'}</span>
                  <span>·</span>
                  <span>{item.size ? convertBinaryByte(item.size) : '-'}</span>
                  {item.created_at && (
                    <>
                      <span>·</span>
                      <span>{convertLocalTime(item.created_at)}</span>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 변환 모달 ── */}
      {isTransformModalOpen && (
        <div className={cx('modal-overlay')}>
          <div className={cx('transform-modal')}>
            <div className={cx('modal-header')}>
              <span className={cx('modal-title')}>학습 데이터셋 생성</span>
              <button className={cx('modal-close')} onClick={() => { setIsTransforming(false); onCloseTransformModal(); }}>
                <img src={closeIcon} alt="닫기" />
              </button>
            </div>
            <div className={cx('modal-body')}>
              <div className={cx('form-group')}>
                <label className={cx('form-label')}>입력 데이터셋</label>
                <Selectbox
                  size='medium'
                  list={datasetOptions}
                  selectedItem={selectedDataset}
                  onChange={(val) => setSelectedDataset(val)}
                  customStyle={{ selectboxForm: { width: '100%' }, listForm: { width: '100%' } }}
                  t={t}
                />
              </div>
              <div className={cx('form-group')}>
                <label className={cx('form-label')}>출력 포맷</label>
                <div className={cx('fmt-check-grid')}>
                  {['JSON', 'CSV', 'Parquet', 'JSONL'].map((fmt) => (
                    <label key={fmt} className={cx('fmt-check-item', outputFormats[fmt] && 'checked')} onClick={() => handleFormatChange(fmt)}>
                      <span className={cx('check-box', outputFormats[fmt] && 'on')} />
                      <span className={cx('check-label')}>{fmt}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className={cx('pipeline-preview')}>
                <div className={cx('pipe-node', 'pipe-source')}>
                  📦 {selectedDataset?.label || '데이터셋 선택'}
                </div>
                <div className={cx('pipe-arrow')}>→</div>
                <div className={cx('pipe-node', 'pipe-target')}>
                  🎓 학습 데이터셋<br />
                  <small>{Object.entries(outputFormats).filter(([,v]) => v).map(([k]) => k).join(' · ') || '포맷 선택'}</small>
                </div>
              </div>
            </div>
            <div className={cx('modal-footer')}>
              <button
                className={cx('cancel-btn')}
                onClick={() => { setIsTransforming(false); onCloseTransformModal(); }}
              >
                취소
              </button>
              <button
                className={cx('start-btn', (isTransforming || !isAnyFormatSelected) && 'disabled')}
                onClick={handleStartTransformation}
                disabled={isTransforming || !isAnyFormatSelected}
              >
                {isTransforming ? '변환 중...' : '변환 시작'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserDatasetContent;
