import { useTranslation } from 'react-i18next';

import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

// Components
import ListLoading from '../../admin/AdminNodeContent/nodeComponent/NodeRateList/ListLoading';

// CSS Module
import classNames from 'classnames/bind';
import style from './TotalInstance.module.scss';

const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용되는 비율 목록 컴포넌트
 * @param {{
 *  title: string,
 *  listData: [ { name: string, used: number, total: number } ],
 * }} props
 */
function TotalInstance({ title, listData, columns = [], toolTipIndex }) {
  const { t } = useTranslation();

  return (
    <div className={cx('node-rate-list')}>
      <div className={cx('title')}>{title}</div>
      <div className={cx('table')}>
        <div className={cx('thead')}>
          <div className={cx('tr')}>
            {columns.map(({ label, headStyle }, key) => (
              <div key={key} className={cx('td')} style={headStyle}>
                {label}
              </div>
            ))}
          </div>
        </div>
        <div className={cx('tbody')}>
          {listData === null && <ListLoading />}
          {listData &&
            listData.length > 0 &&
            listData.map((d, i) => {
              const gpuName = d.gpu_resource_group_name || d.gpu_name || '';
              return (
                <div key={i} className={cx('tr')}>
                  {columns.map(
                    ({ bodyStyle, selector, cell, isUsedBar }, key) => (
                      <div key={key} className={cx('td')} style={bodyStyle}>
                        {!isUsedBar && cell && cell(d)}

                        {isUsedBar && cell && (
                          <div className={cx('bar-container')}>
                            <div className={cx('text-container')}>
                              <span className={cx('text')}>
                                {t('total.label')}
                              </span>
                              <span className={cx('total')}>
                                {d.instance_allocate} EA
                              </span>
                            </div>
                            {cell(d)}
                          </div>
                        )}

                        {!cell && (
                          <span className={cx('element')}>{d[selector]}</span>
                        )}

                        <div className={cx('element')}>
                          {key === toolTipIndex && d[selector] && (
                            <InstanceTooltip
                              instanceType={gpuName ? 'GPU' : 'CPU'}
                              gpuName={gpuName}
                              gpuAllocateNum={d.gpu_allocate}
                              cpuAllocateNum={d.cpu_allocate}
                              ramAllocateNum={d.ram_allocate}
                              contentsCustomStyle={{
                                minWidth: '120px',
                                transform: ' translate(30px, -60px)',
                              }}
                              iconCustomStyle={{ marginLeft: '4px' }}
                            />
                          )}
                        </div>
                      </div>
                    ),
                  )}
                </div>
              );
            })}
          {listData && listData.length === 0 && (
            <div className={cx('no-data')}>
              <span>{t('noData.message')}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TotalInstance;
