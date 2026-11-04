import React from 'react';

import Info from './Info';
import InstanceSetting from './InstanceSetting';

import classNames from 'classnames/bind';
import style from './DataInfo.module.scss';

const cx = classNames.bind(style);

export default function DataInfo({ info }) {
  const { collect_info, instance_info, instance_usage_info } = info;

  const {
    description,
    dataset_name,
    dataset_path,
    collect_cycle,
    collect_cycle_unit,
    collect_storage_limit,
    collect_storage_unit,
    access,
    owner,
    members,
    start_datetime,
    create_datetime,
  } = collect_info;

  const { instance_name, instance_count } = instance_info;

  return (
    <div className={cx('flex-24')}>
      <Info
        description={description}
        dataset_name={dataset_name}
        dataset_path={dataset_path}
        collect_cycle={collect_cycle}
        collect_cycle_unit={collect_cycle_unit}
        collect_storage_limit={collect_storage_limit}
        collect_storage_unit={collect_storage_unit}
        access={access}
        owner={owner}
        members={members}
        create_datetime={create_datetime}
        start_datetime={start_datetime}
      />
      <InstanceSetting
        instance_name={instance_name}
        instance_count={instance_count}
        instance_usage_info={instance_usage_info}
      />
    </div>
  );
}
