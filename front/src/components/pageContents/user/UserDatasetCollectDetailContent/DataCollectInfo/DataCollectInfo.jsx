import React from 'react';

import DataInfo from './DataInfo';
import DataList from './DataList';

// CSS Module
import classNames from 'classnames/bind';
import style from './DataCollectInfo.module.scss';

const cx = classNames.bind(style);

const calColumns = (collect_method) => {
  if (collect_method === 'public_api') {
    return ['API 이름', 'API URL', 'API Key', '제공 기관', '상세 설명 페이지'];
  }

  if (collect_method === 'remote_server') {
    return ['원격 서버 이름', '원격 서버 URL', 'ID', '수집 데이터 경로'];
  }
  if (collect_method === 'crawling') {
    return ['웹 크롤러 이름', '웹 크롤러 URL'];
  }
  return ['배포 프로젝트', '프로젝트 생성자'];
};

const calData = (list, collect_method) => {
  if (collect_method === 'public_api') {
    const shallowList = list.slice();
    const transfromList = shallowList.map((info) => {
      return {
        ...info,
        first: info.name,
        second: info.url,
        third: (
          <input
            type='password'
            value='1234566790'
            style={{
              width: '50px',
              border: 'none',
              textAlign: 'center',
              cursor: 'pointer',
              backgroundColor: '#fff',
            }}
            disabled
          />
        ),
        fourth: info.providing_organization,
        five: info.detail_url,
        infoData: {
          ...info,
        },
      };
    });
    return transfromList;
  }
  if (collect_method === 'crawling') {
    const shallowList = list.slice();
    const transformList = shallowList.map(({ name, url }) => ({
      first: name,
      second: url,
    }));
    return transformList;
  }
  if (collect_method === 'remote_server') {
    const shallowList = list.slice();
    const transformList = shallowList.map(({ name, ip, user, path }) => ({
      first: name,
      second: ip,
      third: user,
      fourth: path,
    }));
    return transformList;
  }

  const shallowList = list.slice();
  return shallowList.map((item) => {
    return {
      first: item.name,
      second: item.user_name,
    };
  });
};

export default function DataCollectInfo({ info }) {
  const { collect_method, collect_information_list } = info.collect_info;

  const columns = calColumns(collect_method);
  const data = calData(collect_information_list, collect_method);

  return (
    <div className={cx('info-cont')}>
      <DataInfo info={info} />
      <DataList data={data} columns={columns} collect_method={collect_method} />
    </div>
  );
}
