import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import LatestJob from '@src/components/organisms/Dashboard/LatestJob';

import classNames from 'classnames/bind';
// CSS module
import style from './JobList.module.scss';

const cx = classNames.bind(style);

const JobList = ({ trainingItems }) => {
  const { t } = useTranslation();
  const [scrollPosition, setScrollPosition] = useState(0);
  const jobListRef = useRef(null);

  const handleScroll = () => {
    if (jobListRef.current) {
      const scrollTop = jobListRef.current.scrollTop;
      setScrollPosition(scrollTop);
    }
  };

  useEffect(() => {
    const jobListNode = jobListRef.current;
    if (jobListNode) {
      jobListNode.addEventListener('scroll', handleScroll);
      return () => {
        jobListNode.removeEventListener('scroll', handleScroll);
      };
    }
  }, []);

  const latestJobList = trainingItems.map(
    (
      {
        type,
        name,
        status_hps,
        status_job,
        status_tool,
        status_deployment,
        instance,
        worker_list,
        tool_list,
        job_list,
      },
      index,
    ) => (
      <LatestJob
        key={index}
        order={index}
        name={name}
        type={type}
        statusHps={status_hps}
        statusJob={status_job}
        statusTool={status_tool}
        statusDeployment={status_deployment}
        instance={instance}
        workerList={worker_list}
        toolList={tool_list}
        job_list={job_list ? job_list : []}
        t={t}
        scrollPosition={scrollPosition}
      />
    ),
  );

  return (
    <div className={cx('job-list')} ref={jobListRef}>
      {latestJobList}
    </div>
  );
};

export default JobList;
