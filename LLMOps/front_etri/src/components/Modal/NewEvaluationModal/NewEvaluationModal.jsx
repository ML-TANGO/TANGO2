import { useState } from 'react';
import classNames from 'classnames/bind';
import style from './NewEvaluationModal.module.scss';

const cx = classNames.bind(style);

const EVAL_TYPES = [
  {
    id: 'expert',
    name: '전문가 평가',
    icon: '👩‍💼',
    description: '도메인 전문가가 모델 출력을 직접 검토하고 O/X로 평가합니다.',
    example: 'SDS Dataset 기반 VLM 전문가 평가',
  },
  {
    id: 'benchmark',
    name: '벤치마크',
    icon: '📊',
    description: 'MixATIS, LogicKor 등 표준 데이터셋과 METEOR, CIDEr, SPICE 등 정량 메트릭으로 자동 평가합니다.',
    example: 'MixATIS / METEOR + CIDEr',
  },
  {
    id: 'llm_judge',
    name: 'LLM-as-a-Judge',
    icon: '🤖',
    description: 'ChatGPT, Claude, Gemini 등 상용 LLM 또는 로컬 LLM을 심사관으로 활용하여 모델 출력을 평가합니다.',
    example: 'Claude 기반 자동 품질 평가',
  },
];

export default function NewEvaluationModal({ onClose, onSelect }) {
  const [selected, setSelected] = useState(null);

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('header')}>
          <span className={cx('title')}>New Evaluation</span>
          <button className={cx('close-btn')} onClick={onClose}>✕</button>
        </div>
        <p className={cx('sub')}>평가 방식을 선택하세요</p>
        <div className={cx('type-grid')}>
          {EVAL_TYPES.map((t) => (
            <div
              key={t.id}
              className={cx('type-card', selected === t.id && 'selected')}
              onClick={() => setSelected(t.id)}
            >
              <div className={cx('type-icon')}>{t.icon}</div>
              <div className={cx('type-name')}>{t.name}</div>
              <div className={cx('type-desc')}>{t.description}</div>
              <div className={cx('type-example')}>예시: {t.example}</div>
            </div>
          ))}
        </div>
        <div className={cx('footer')}>
          <button className={cx('cancel-btn')} onClick={onClose}>취소</button>
          <button
            className={cx('confirm-btn', !selected && 'disabled')}
            disabled={!selected}
            onClick={() => selected && onSelect(selected)}
          >
            선택
          </button>
        </div>
      </div>
    </div>
  );
}
