import { useState, useEffect } from 'react';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './ModelSelector.module.scss';

const cx = classNames.bind(style);

function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

function CheckpointList({ modelId, onCheckpointSelect }) {
  const [commits, setCommits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!modelId) return;
    setLoading(true);
    setSelected(null);
    callApi({ url: `models/commit-models?model_id=${modelId}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result?.list) ? [...res.result.list] : [];
        list.sort((a, b) => (b.commit_datetime ?? '').localeCompare(a.commit_datetime ?? ''));
        setCommits(list);
      }
      setLoading(false);
    });
  }, [modelId]);

  const handleSelect = (commit) => {
    setSelected(commit.id);
    onCheckpointSelect?.(commit.id, commit);
  };

  if (loading) {
    return <p className={cx('ckpt-status')}>체크포인트 로딩 중...</p>;
  }
  if (!commits.length) {
    return <p className={cx('ckpt-status', 'ckpt-status--empty')}>저장된 체크포인트가 없습니다.</p>;
  }

  return (
    <div className={cx('ckpt-list')}>
      {commits.map((commit, i) => (
        <button
          key={commit.id}
          type="button"
          className={cx('ckpt-item', selected === commit.id && 'ckpt-item--selected')}
          onClick={() => handleSelect(commit)}
        >
          <div className={cx('ckpt-row')}>
            <span className={cx('ckpt-name')}>{commit.name ?? '-'}</span>
            {i === 0 && <span className={cx('ckpt-latest')}>최신</span>}
          </div>
          {commit.commit_message && (
            <div className={cx('ckpt-msg')}>{commit.commit_message}</div>
          )}
          <div className={cx('ckpt-meta')}>
            {commit.create_user_name && <span>{commit.create_user_name}</span>}
            {commit.commit_datetime && <span>{formatDate(commit.commit_datetime)}</span>}
          </div>
        </button>
      ))}
    </div>
  );
}

function InfoPanel({ model, onCheckpointSelect }) {
  if (!model) {
    return (
      <div className={cx('info-empty')}>
        <span className={cx('info-empty-text')}>목록에서 모델을 선택하세요</span>
      </div>
    );
  }

  return (
    <div className={cx('info-panel')}>
      <div className={cx('info-header')}>
        <span className={cx('info-name')}>{model.name}</span>
        <div className={cx('info-badges')}>
          {model.is_finetuned && <span className={cx('badge', 'badge-fine')}>Fine-tuned</span>}
          {model.status?.fine_tuning === 'running' && (
            <span className={cx('badge', 'badge-running')}>학습 중</span>
          )}
          {model.bookmark && <span className={cx('badge', 'badge-bookmark')}>★ 즐겨찾기</span>}
        </div>
      </div>

      <div className={cx('info-desc')}>{model.description || '설명 없음'}</div>

      <div className={cx('info-meta-grid')}>
        {model.size && (
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>크기</span>
            <span className={cx('meta-value')}>{model.size}</span>
          </div>
        )}
        {model.type && (
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>타입</span>
            <span className={cx('meta-value')}>{model.type}</span>
          </div>
        )}
        {model.create_user_name && (
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>생성자</span>
            <span className={cx('meta-value')}>{model.create_user_name}</span>
          </div>
        )}
        <div className={cx('meta-item')}>
          <span className={cx('meta-label')}>생성일</span>
          <span className={cx('meta-value')}>{formatDate(model.create_datetime)}</span>
        </div>
        {model.update_datetime && (
          <div className={cx('meta-item')}>
            <span className={cx('meta-label')}>수정일</span>
            <span className={cx('meta-value')}>{formatDate(model.update_datetime)}</span>
          </div>
        )}
        {model.users?.length > 0 && (
          <div className={cx('meta-item', 'meta-item--full')}>
            <span className={cx('meta-label')}>접근 사용자</span>
            <span className={cx('meta-value')}>{model.users.map((u) => u.user_name).join(', ')}</span>
          </div>
        )}
      </div>

      <div className={cx('ckpt-section')}>
        <div className={cx('ckpt-section-title')}>커밋된 체크포인트</div>
        <CheckpointList modelId={model.id} onCheckpointSelect={onCheckpointSelect} />
      </div>
    </div>
  );
}

export default function ModelSelector({ wid, selected, onSelect, onCheckpointSelect }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState(null);

  useEffect(() => {
    if (!wid) return;
    callApi({ url: `models?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result) ? res.result : (res.result?.list ?? []);
        setModels(list);
        if (selected) setSelectedModel(list.find((m) => m.id === selected) ?? null);
      }
      setLoading(false);
    });
  }, [wid]);

  useEffect(() => {
    if (selected && models.length) {
      setSelectedModel(models.find((m) => m.id === selected) ?? null);
    } else if (!selected) {
      setSelectedModel(null);
    }
  }, [selected, models]);

  const handleSelect = (m) => {
    setSelectedModel(m);
    onSelect(m.id, m);
  };

  if (loading) return <div className={cx('status-msg')}>모델 목록 로딩 중...</div>;
  if (!models.length) return <div className={cx('status-msg')}>학습된 모델이 없습니다.</div>;

  return (
    <div className={cx('container')}>
      <div className={cx('listbox')}>
        {models.map((m) => (
          <button
            key={m.id}
            type="button"
            className={cx('list-item', selected === m.id && 'list-item--selected')}
            onClick={() => handleSelect(m)}
          >
            <div className={cx('item-row')}>
              <span className={cx('item-name')}>{m.name}</span>
              <div className={cx('item-badges')}>
                {m.is_finetuned && <span className={cx('badge', 'badge-fine')}>FT</span>}
                {m.status?.fine_tuning === 'running' && (
                  <span className={cx('badge', 'badge-running')}>학습 중</span>
                )}
              </div>
            </div>
            <div className={cx('item-desc')}>{m.description || '-'}</div>
            {(m.size || m.type) && (
              <div className={cx('item-meta')}>
                {m.size && <span>{m.size}</span>}
                {m.type && <span>{m.type}</span>}
              </div>
            )}
          </button>
        ))}
      </div>

      <div className={cx('divider')} />

      <InfoPanel model={selectedModel} onCheckpointSelect={onCheckpointSelect} />
    </div>
  );
}
