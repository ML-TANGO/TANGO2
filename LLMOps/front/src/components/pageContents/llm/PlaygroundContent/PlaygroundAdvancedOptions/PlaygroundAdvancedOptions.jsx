import PlaygroundFrame from '../PlaygroundFrame';

import classNames from 'classnames/bind';
import style from './PlaygroundAdvancedOptions.module.scss';

const cx = classNames.bind(style);

// 배포 고급 옵션(양자화 / RAG / 최적화) — 현재 비활성 자리표시(선택 기능 미구현).
//   칩은 시각적으로만 노출하고 pointer-events/ disabled 로 상호작용 차단 → "준비 중".
const OPTION_GROUPS = [
  { label: '양자화 옵션', options: ['INT8', 'INT4', 'FP16', 'BF16'] },
  { label: 'RAG', options: ['없음', '기본 RAG', '고급 RAG'] },
  {
    label: '최적화 옵션',
    options: [
      'Flash Attention',
      'Continuous Batching',
      'KV Cache 최적화',
      'Tensor Parallelism',
    ],
  },
];

export default function PlaygroundAdvancedOptions() {
  return (
    <PlaygroundFrame style={{ backgroundColor: '#fff' }}>
      <div className={cx('header')}>
        <h3 className={cx('title')}>고급 옵션</h3>
        <span className={cx('badge')}>준비 중</span>
      </div>
      <div className={cx('groups')}>
        {OPTION_GROUPS.map((group) => (
          <div className={cx('group')} key={group.label}>
            <span className={cx('group-label')}>{group.label}</span>
            <div className={cx('options')}>
              {group.options.map((opt) => (
                <button
                  key={opt}
                  type='button'
                  className={cx('option')}
                  disabled
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </PlaygroundFrame>
  );
}
