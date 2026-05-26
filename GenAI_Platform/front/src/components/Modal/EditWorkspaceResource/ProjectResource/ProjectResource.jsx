import { useTranslation } from 'react-i18next';

import Dropdown from '@src/components/atoms/Dropdown';

import RangeBar from '../RangeBar';

import classNames from 'classnames/bind';
import style from './ProjectResource.module.scss';

const cx = classNames.bind(style);

const ProjectResource = ({
  projectInfoList,
  range,
  maxRange,
  handleProejectItem,
  handleRangeBar,
}) => {
  const { t } = useTranslation();

  const { item_type, value } = range;

  const rangeLabel = {
    project: 'learningResourceManagement.label',
    deployment: 'deploymentResourceManagement.label',
    preprocessing: 'preprocessingResourceManagement.label',
  };

  return (
    <div className={cx('cont')}>
      <h3 className={cx('project-select-label')}>프로젝트 선택</h3>
      <Dropdown
        value={value}
        list={projectInfoList}
        handleOptionClick={handleProejectItem}
        placeholder={t('project.select.label')}
      />
      {range.label && (
        <>
          <p className={cx('project-title-txt')}>{t(rangeLabel[item_type])}</p>
          <div className={cx('body-cont')}>
            {(item_type === 'project' || item_type === 'preprocessing') && (
              <div className={cx('first-body-cont')}>
                <p className={cx('title')}>{t('learningToolLimit.label')}</p>
                <div className={cx('flex-row')}>
                  <RangeBar
                    label={'CPU Cores'}
                    setting={'tool_cpu_limit'}
                    range={range}
                    handleRangeBar={handleRangeBar}
                    max={maxRange.cpu}
                    step={1}
                    unit={t('eaOnly.label')}
                  />
                  <RangeBar
                    label={'RAM'}
                    setting={'tool_ram_limit'}
                    range={range}
                    handleRangeBar={handleRangeBar}
                    max={maxRange.ram}
                    unit={'GB'}
                  />
                </div>
                <div className={cx('border')} />
                <p className={cx('title')}>{t('jobToolLimit.label')}</p>
                <div className={cx('flex-row')}>
                  <RangeBar
                    label={'CPU Cores'}
                    setting={'job_cpu_limit'}
                    range={range}
                    handleRangeBar={handleRangeBar}
                    max={maxRange.cpu}
                    unit={'개'}
                  />
                  <RangeBar
                    label={'RAM'}
                    setting={'job_ram_limit'}
                    range={range}
                    handleRangeBar={handleRangeBar}
                    max={maxRange.ram}
                    unit={'GB'}
                  />
                </div>
              </div>
            )}
            {item_type === 'deployment' && (
              <>
                <div className={cx('second-body-cont')}>
                  <p className={cx('title')}>{t('workerToolLimit.label')}</p>
                  <div className={cx('flex-row')}>
                    <RangeBar
                      label={'CPU Cores'}
                      setting={'deployment_cpu_limit'}
                      range={range}
                      handleRangeBar={handleRangeBar}
                      max={maxRange.cpu}
                      unit={'개'}
                    />
                    <RangeBar
                      label={'RAM'}
                      setting={'deployment_ram_limit'}
                      range={range}
                      handleRangeBar={handleRangeBar}
                      max={maxRange.ram}
                      unit={'GB'}
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ProjectResource;
