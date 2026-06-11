import { useState, useEffect } from 'react';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './ModelSelector.module.scss';

const cx = classNames.bind(style);

export default function ModelSelector({ wid, selected, onSelect }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!wid) return;
    callApi({ url: `models?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result) ? res.result : (res.result?.list ?? []);
        setModels(list);
      }
      setLoading(false);
    });
  }, [wid]);

  if (loading) return <div className={cx('loading')}>모델 목록 로딩 중...</div>;
  if (!models.length) return <div className={cx('empty')}>학습된 모델이 없습니다.</div>;

  return (
    <div className={cx('grid')}>
      {models.map((m) => (
        <div
          key={m.id}
          className={cx('card', selected === m.id && 'selected')}
          onClick={() => onSelect(m.id, m)}
        >
          <div className={cx('row')}>
            <span className={cx('name')}>{m.name}</span>
            {m.is_finetuned && <span className={cx('badge')}>Fine-tuned</span>}
          </div>
          <div className={cx('desc')}>{m.description || '-'}</div>
          <div className={cx('meta')}>
            {m.size && <span>{m.size}</span>}
            {m.type && <span>{m.type}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
