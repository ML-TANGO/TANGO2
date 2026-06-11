import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, ButtonV2, Selectbox, Checkbox } from '@tango/ui-react';

import PageTitle from '@src/components/atoms/PageTitle';
import DatasetCheckModalContainer from '@src/components/Modal/DatasetCheckModal/DatasetCheckModalContainer';
import Table from '@src/components/molecules/Table';
import { toast } from '@src/components/Toast';

import classNames from 'classnames/bind';
// CSS module
import style from './UserDatasetContent.module.scss';

// Icons
import fileIcon from '@src/static/images/icon/file.svg';
import closeIcon from '@src/static/images/icon/00-ic-black-close.svg';

const cx = classNames.bind(style);

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

  const [isTransforming, setIsTransforming] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [outputFormats, setOutputFormats] = useState({
    JSON: true,
    CSV: false,
    Parquet: false,
    JSONL: false,
  });

  const datasetOptions = datasets.map((item) => ({
    label: item.dataset_name,
    value: item.id,
  }));

  useEffect(() => {
    if (isTransformModalOpen) {
      setOutputFormats({
        JSON: true,
        CSV: false,
        Parquet: false,
        JSONL: false,
      });
      if (datasets && datasets.length > 0) {
        const options = datasets.map((item) => ({
          label: item.dataset_name,
          value: item.id,
        }));
        const found = options.find((opt) => opt.label === 'SDS Dataset') || options[0];
        setSelectedDataset(found);
      } else {
        setSelectedDataset(null);
      }
    }
  }, [isTransformModalOpen, datasets]);

  const handleFormatChange = (format) => {
    setOutputFormats((prev) => ({
      ...prev,
      [format]: !prev[format],
    }));
  };

  const isAnyFormatSelected = Object.values(outputFormats).some((val) => val);

  const handleStartTransformation = () => {
    setIsTransforming(true);
    setTimeout(() => {
      setIsTransforming(false);
      toast.success('Transformation completed');
      onCloseTransformModal();
    }, 1500);
  };

  const handleCloseModal = () => {
    setIsTransforming(false);
    onCloseTransformModal();
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

  const filterList = (
    <div className={cx('btn-filter')}>
      {/* <Button
        type='primary-light'
        size='medium'
        onClick={onAllSync}
        iconAlign='left'
        icon={loading ? loadingIcon : syncIcon}
        customStyle={{ width: '100%' }}
      >
        {t('syncAll.label')}
      </Button> */}
      <Selectbox
        size='medium'
        list={accessTypeOptions}
        selectedItem={accessType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onAccessTypeChange}
        t={t}
      />
    </div>
  );

  const topButtonList = (
    <>
      {/* <Button type='primary' onClick={() => onCreate()}>
        {t('createDataset.label')}
      </Button> */}
      <div>
        {/* <Button
          type='primary-light'
          onClick={builtInModalOpenHandler}
          iconAlign='right'
          icon={
            builtInModalOpen
              ? '/images/icon/00-ic-basic-arrow-02-up-blue.svg'
              : '/images/icon/00-ic-basic-arrow-02-down-blue.svg'
          }
        >
          {t('builtInModelDataset.label')}
        </Button> */}
        <div className={cx('modal-wrap')}>
          {builtInModalOpen && (
            <DatasetCheckModalContainer
              list={builtInModelList}
              closeFunc={builtInModalOpenHandler}
              submit={{
                func: builtInTemplateOpen,
                text: t('openTemplate.label'),
              }}
            />
          )}
        </div>
      </div>
    </>
  );

  const bottomButtonList = (
    <>
      <button
        onClick={openDeleteConfirmPopup}
        className={cx('delete-btn', deleteBtnDisabled && 'disabled')}
        disabled={deleteBtnDisabled}
      >
        {t('delete.label')}
      </button>
    </>
  );

  return (
    <div id='UserDatasetContent' className={cx('wrapper')}>
      <div className={cx('page-header')}>
        <PageTitle>{t('datasetManagement.label')}</PageTitle>
        <div className={cx('btn')}>
          <ButtonV2
            colorType='skyblue'
            size='m'
            label={t('dataResourceManagementSettings.label')}
            disabled={true}
            onClick={() => onClickDataResourceSetting()}
          />
          <button
            className={cx('create-btn')}
            onClick={() => {
              onCreate();
            }}
          >
            {t('createDataset.label')}
          </button>
        </div>
      </div>
      {/* {IS_MARKER && MARKER_VERSION === '2' && (
        <div className={cx('marker-btn')}><NewMarkerBtn /></div>
      )} */}
      <div className={cx('content')}>
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
          selectableRowDisabled={({ permission_level: permissionLevel }) =>
            permissionLevel > 3
          }
          searchOptions={searchOptions}
          searchKey={searchKey}
          keyword={keyword}
          onSearchKeyChange={onSearchKeyChange}
          onSearch={(e) => {
            onSearch(e.target.value);
          }}
          onClear={onClear}
          onSortHandler={onSortHandler}
        />
      </div>

      {/* Transformation Section */}
      <div className={cx('section-divider')} />
      <div className={cx('page-header')}>
        <PageTitle>Transformation</PageTitle>
        <div className={cx('btn')}>
          <button
            className={cx('create-btn')}
            onClick={() => {
              if (transformations && transformations.length > 0) {
                onOpenTransformModal(transformations[0]);
              }
            }}
          >
            Create Dataset
          </button>
        </div>
      </div>
      <div className={cx('content')}>
        <Table
          columns={transformColumns}
          data={transformations}
          totalRows={transformations.length}
          onRowClick={onTransformRowClick}
        />
      </div>

      {/* Transformation Modal */}
      {isTransformModalOpen && selectedTransformItem && (
        <div className={cx('modal-overlay')}>
          <div className={cx('transform-modal')}>
            <div className={cx('modal-header')}>
              <h3>Create Dataset</h3>
              <button className={cx('close-x-btn')} onClick={handleCloseModal}>
                <img src={closeIcon} alt="close" />
              </button>
            </div>
            <div className={cx('modal-body')}>
              <div className={cx('form-row')}>
                <span className={cx('form-label')}>Input Dataset</span>
                <div className={cx('selectbox-container')}>
                  <Selectbox
                    size='medium'
                    list={datasetOptions}
                    selectedItem={selectedDataset}
                    onChange={(val) => setSelectedDataset(val)}
                    customStyle={{
                      selectboxForm: {
                        width: '100%',
                      },
                      listForm: {
                        width: '100%',
                      },
                    }}
                    t={t}
                  />
                </div>
              </div>
              <div className={cx('form-row')}>
                <span className={cx('form-label')}>Output Format</span>
                <div className={cx('checkbox-grid')}>
                  <Checkbox
                    label="JSON"
                    checked={outputFormats.JSON}
                    onChange={() => handleFormatChange('JSON')}
                  />
                  <Checkbox
                    label="CSV"
                    checked={outputFormats.CSV}
                    onChange={() => handleFormatChange('CSV')}
                  />
                  <Checkbox
                    label="Parquet"
                    checked={outputFormats.Parquet}
                    onChange={() => handleFormatChange('Parquet')}
                  />
                  <Checkbox
                    label="JSONL"
                    checked={outputFormats.JSONL}
                    onChange={() => handleFormatChange('JSONL')}
                  />
                </div>
              </div>
            </div>
            <div className={cx('modal-footer')}>
              <button className={cx('cancel-btn')} onClick={handleCloseModal}>
                Cancel
              </button>
              <button
                className={cx('start-btn')}
                onClick={handleStartTransformation}
                disabled={isTransforming || !isAnyFormatSelected}
              >
                {isTransforming ? 'Transforming...' : 'Start Transformation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserDatasetContent;
