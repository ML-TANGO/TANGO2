import React from 'react';

import ModelCard from './ModelCard';
import PlaygroundCard from './PlaygroundCard';
import RagCard from './RagCard';

// CSS Module
import classNames from 'classnames/bind';
import style from './ProjectCardList.module.scss';

const cx = classNames.bind(style);

export default function ProjectCardList({ project_items }) {
  if (project_items.length === 0 || !Array.isArray(project_items))
    return <div className={cx('center')}>데이터가 없습니다.</div>;
  return (
    <div className={cx('list-cont')}>
      {project_items.map((info, idx) => {
        if (info.type === 'rag') return <RagCard key={idx} info={info} />;
        if (info.type === 'playground')
          return <PlaygroundCard key={idx} info={info} />;
        return <ModelCard key={idx} info={info} />;
      })}
    </div>
  );
}
