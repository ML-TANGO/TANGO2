import { useTranslation } from 'react-i18next';

import Card from './Card';
import GpuListItem from './GpuListItem';

import classNames from 'classnames/bind';
import style from './ResourceSetting.module.scss';

const cx = classNames.bind(style);

const ResourceSetting = ({
  // ** 인스턴스 할당......... (가져다 붙입니다) **
  isInstance,
  models,
  checkboxHandler,
  gpuSelectedOptions,
  onChangeGpuInputValue,
  inputValue,
  edit,
  type,
  colList,
  rowList,
  isReadOnly = false,
  // ** 스토리지 할당...**
  isStorage,
  list,
  prevStorageModel,
  storageSelectHandler,
  workspaceUsage,
  storageInputValueHandler,
  mainStorageSelectedModel,
  dataStorageSelectedModel,
  mainStorageValue,
  dataStorageValue,
  prevMainStorage,
  prevDataStorage,
  totalStorageInputValue,
  isMainStorageDisabled = false,
  isDataStorageDisabled = false,
  prevMainStorageVolume,
  prevDataStorageVolume,
}) => {
  const { t } = useTranslation();

  const isDeployment = type.includes('DEPLOYMENT');
  const isTraining = type.includes('gpu');

  return (
    <div className={cx('wrapper')}>
      {isInstance && (
        <>
          <div className={cx('header')}>{t('instanceAllocation.label')}</div>
          <div
            className={cx(
              'list-header',
              isDeployment && 'deployment',
              isTraining && 'training',
            )}
          >
            {colList && colList.length > 0 ? (
              colList.map((v, index) => {
                if (index === 0) {
                  return <div key={index}>{v}</div>;
                }
                return (
                  <div key={index} className={cx('sub-col')}>
                    {v}
                  </div>
                );
              })
            ) : (
              <>
                <div>{t('instanceName.label')}</div>
                <div className={cx('sub-col')}>
                  <div>{t('totalAmount.label')}</div>
                </div>
                {!isDeployment && (
                  <div className={cx('sub-col')}>
                    <div>{t('availableCapacity.label')}</div>
                  </div>
                )}
                <div className={cx('sub-col')}>
                  <div>{t('allocation.label')}</div>
                </div>
              </>
            )}
          </div>
          <ul className={cx('list-body')}>
            {models && models.length > 0 ? (
              models.map(
                (
                  {
                    resource_name: ResourceName,
                    name = '',
                    avail,
                    total,
                    free,
                    ram,
                    cpu,
                    gpu,
                    allocate,
                    gpu_name: gpuName,
                    used,
                  },
                  idx,
                ) => {
                  let newName = ResourceName ? ResourceName : name;

                  return (
                    <GpuListItem
                      listLength={models.length}
                      key={idx}
                      idx={idx}
                      model={newName}
                      gpuName={gpuName}
                      ram={ram}
                      cpu={cpu}
                      gpu={gpu}
                      avail={avail}
                      total={
                        typeof total === 'number' && total ? total : allocate
                      }
                      free={free === undefined ? total : free}
                      selected={
                        gpuSelectedOptions[idx]
                          ? gpuSelectedOptions[idx][idx]
                          : false
                      }
                      edit={edit}
                      inputValue={inputValue[idx]}
                      list={rowList}
                      checkboxHandler={checkboxHandler}
                      onChangeInputValue={onChangeGpuInputValue}
                      type={type}
                      isReadOnly={isReadOnly}
                      used={used}
                      customStyle={{
                        display: 'grid',
                        gridTemplateColumns:
                          isDeployment || isTraining
                            ? '50% 25% 25%'
                            : '44% 16% 16% 24%',
                      }}
                    />
                  );
                },
              )
            ) : (
              <div className={cx('empty-item')}>{t('noData.message')}</div>
            )}
          </ul>
        </>
      )}
      {/* ** 스토리지 ** */}
      {isStorage && (
        <>
          <div className={cx('container')}>
            <div className={cx('main-title')}>
              Main Storage {t('allocateGpu.label')}
            </div>
            <div className={cx('sub-title')}>
              <div className={cx('card-header')}>
                <div className={cx('sub-col')}>{t('type.label')}</div>
                <div> {t('name.label')}</div>
                <div className={cx('sub-col')}>
                  {t('workspaceStorageTotal.label')}
                </div>
                <div className={cx('sub-col')}>
                  {t('storageRemaining.modal.label')}
                </div>
                <div className={cx('sub-col')}>
                  {t('allocationCapacity.label')}
                </div>
              </div>
            </div>
            <ul className={cx('card-list')}>
              <div className={cx('list-body')}>
                {!list || list?.length === 0 ? (
                  <div className={cx('no-data')}> {t('noData.message')} </div>
                ) : (
                  list.map((m, key) => {
                    let mainStorageFreeSize =
                      m.free_size +
                      (prevDataStorageVolume + prevMainStorageVolume);
                    const inputMaxValue =
                      mainStorageFreeSize - dataStorageValue;

                    if (
                      m.id === mainStorageSelectedModel?.id ||
                      m.id === dataStorageSelectedModel?.id
                    ) {
                      mainStorageFreeSize -=
                        mainStorageValue + dataStorageValue;
                    }

                    const inputValue =
                      m.id === mainStorageSelectedModel?.id
                        ? mainStorageValue
                        : 0;

                    return (
                      <Card
                        id={m.id}
                        key={`${key}-main`}
                        idx={key}
                        type={type}
                        model={mainStorageSelectedModel}
                        name={m?.name}
                        storageInputValueHandler={storageInputValueHandler}
                        storageType={'main'}
                        selectHandler={storageSelectHandler}
                        modelOptions={list}
                        capacity={m.size}
                        prevStorageModel={prevStorageModel}
                        storageInputValue={inputValue}
                        freeSize={mainStorageFreeSize}
                        allocateUsed={m?.used_size}
                        totalSize={m?.total_size}
                        systemType={m?.type}
                        workspaceUsage={workspaceUsage}
                        prevStorageSize={prevMainStorage}
                        disabled={isMainStorageDisabled}
                        inputMaxValue={inputMaxValue}
                        t={t}
                      />
                    );
                  })
                )}
              </div>
            </ul>
            <div className={cx('list-border')}></div>
            <div className={cx('main-title')}>
              Data Storage {t('allocateGpu.label')}
            </div>
            <div className={cx('sub-title')}>
              <div className={cx('card-header')}>
                <div className={cx('sub-col')}>{t('type.label')}</div>
                <div> {t('name.label')}</div>
                <div className={cx('sub-col')}>
                  {t('workspaceStorageTotal.label')}
                </div>
                <div className={cx('sub-col')}>
                  {t('storageRemaining.modal.label')}
                </div>
                <div className={cx('sub-col')}>
                  {t('allocationCapacity.label')}
                </div>
              </div>
            </div>
            <ul className={cx('card-list')}>
              <div className={cx('list-body')}>
                {!list || list?.length === 0 ? (
                  <div className={cx('no-data')}> {t('noData.message')} </div>
                ) : (
                  list.map((m, key) => {
                    let dataStorageFreeSize =
                      m.free_size +
                      prevDataStorageVolume +
                      prevMainStorageVolume;
                    const inputMaxValue =
                      dataStorageFreeSize - mainStorageValue;

                    if (
                      m.id === mainStorageSelectedModel?.id ||
                      m.id === dataStorageSelectedModel?.id
                    ) {
                      dataStorageFreeSize -=
                        mainStorageValue + dataStorageValue;
                    }

                    const inputValue =
                      m.id === dataStorageSelectedModel?.id
                        ? dataStorageValue
                        : 0;

                    return (
                      <Card
                        id={m.id}
                        key={`${key}-data`}
                        idx={key}
                        type={type}
                        model={dataStorageSelectedModel} // 선택된 모델.
                        mainStorageValue={mainStorageValue}
                        mainStorageSelectedModel={mainStorageSelectedModel}
                        name={m?.name}
                        storageType={'data'}
                        storageInputValueHandler={storageInputValueHandler}
                        selectHandler={storageSelectHandler}
                        storageInputValue={inputValue}
                        modelOptions={list}
                        capacity={m.size}
                        prevStorageModel={prevStorageModel}
                        freeSize={dataStorageFreeSize}
                        allocateUsed={m?.used_size}
                        totalSize={m?.total_size}
                        systemType={m?.type}
                        workspaceUsage={workspaceUsage}
                        prevStorageSize={prevDataStorage}
                        totalStorageInputValue={totalStorageInputValue}
                        disabled={isDataStorageDisabled}
                        inputMaxValue={inputMaxValue}
                        t={t}
                      />
                    );
                  })
                )}
              </div>
            </ul>
          </div>
        </>
      )}
    </div>
  );
};

export default ResourceSetting;
