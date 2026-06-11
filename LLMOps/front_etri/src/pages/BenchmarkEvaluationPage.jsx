import { useState } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import style from './BenchmarkEvaluationPage.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

const cx = classNames.bind(style);

const DATASETS = [
  { id: 'mixatis',      label: 'MixATIS',      desc: '다중 의도 슬롯 채움 벤치마크' },
  { id: 'logickor',     label: 'LogicKor',      desc: '한국어 추론 능력 평가 데이터셋' },
  { id: 'obj_detect',   label: '객체탐지',      desc: 'COCO 기반 객체 탐지 평가' },
  { id: 'segmentation', label: '세그멘테이션',   desc: '픽셀 단위 분할 정확도 평가' },
  { id: 'ocr',          label: 'OCR',           desc: '문자 인식 정확도 평가' },
];

const METRICS = [
  { id: 'meteor', label: 'METEOR',  desc: '번역/생성 품질 — 단어 정렬 기반' },
  { id: 'cider',  label: 'CIDEr',   desc: '이미지 캡셔닝 품질 — TF-IDF 가중치' },
  { id: 'spice',  label: 'SPICE',   desc: '장면 그래프 기반 의미 유사도' },
  { id: 'bleu',   label: 'BLEU',    desc: 'N-gram 정밀도 기반 번역 품질' },
  { id: 'rouge',  label: 'ROUGE-L', desc: '최장 공통 부분 수열 기반 요약 품질' },
];

export default function BenchmarkEvaluationPage() {
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];

  const [selectedModel, setSelectedModel] = useState(null);
  const [selectedDatasets, setSelectedDatasets] = useState([]);
  const [selectedMetrics, setSelectedMetrics] = useState([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  const toggle = (id, list, setList) => {
    setList((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const canRun = !!selectedModel && selectedDatasets.length > 0 && selectedMetrics.length > 0;

  const handleRun = () => {
    if (!canRun) return;
    setRunning(true);
    setResults(null);
    // mock 3초 후 결과
    setTimeout(() => {
      const mockResults = selectedDatasets.flatMap((ds) =>
        selectedMetrics.map((mt) => ({
          dataset: DATASETS.find((d) => d.id === ds)?.label,
          metric: METRICS.find((m) => m.id === mt)?.label,
          score: (Math.random() * 0.4 + 0.55).toFixed(4),
        })),
      );
      setResults(mockResults);
      setRunning(false);
    }, 3000);
  };

  return (
    <div className={cx('page')}>
      <div className={cx('header')}>
        <button className={cx('back-btn')} onClick={() => history.push(`/user/workspace/${wid}/services`)}>
          ← 목록으로
        </button>
        <h1 className={cx('title')}>벤치마크 평가</h1>
      </div>

      <div className={cx('body')}>
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>평가 대상 모델</h2>
          <ModelSelector
            wid={wid}
            selected={selectedModel}
            onSelect={(id) => setSelectedModel(id)}
          />
        </section>

        <section className={cx('section')}>
          <h2 className={cx('section-title')}>데이터셋 선택</h2>
          <div className={cx('option-grid')}>
            {DATASETS.map((d) => (
              <div
                key={d.id}
                className={cx('option-card', selectedDatasets.includes(d.id) && 'selected')}
                onClick={() => toggle(d.id, selectedDatasets, setSelectedDatasets)}
              >
                <div className={cx('option-name')}>{d.label}</div>
                <div className={cx('option-desc')}>{d.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <section className={cx('section')}>
          <h2 className={cx('section-title')}>평가 메트릭 선택</h2>
          <div className={cx('option-grid')}>
            {METRICS.map((m) => (
              <div
                key={m.id}
                className={cx('option-card', selectedMetrics.includes(m.id) && 'selected')}
                onClick={() => toggle(m.id, selectedMetrics, setSelectedMetrics)}
              >
                <div className={cx('option-name')}>{m.label}</div>
                <div className={cx('option-desc')}>{m.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <div className={cx('run-row')}>
          <button
            className={cx('run-btn', !canRun && 'disabled')}
            disabled={!canRun || running}
            onClick={handleRun}
          >
            {running ? '평가 실행 중...' : '평가 시작'}
          </button>
        </div>

        {results && (
          <section className={cx('section')}>
            <h2 className={cx('section-title')}>평가 결과</h2>
            <table className={cx('result-table')}>
              <thead>
                <tr>
                  <th>데이터셋</th>
                  <th>메트릭</th>
                  <th>점수</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i}>
                    <td>{r.dataset}</td>
                    <td>{r.metric}</td>
                    <td className={cx('score')}>{r.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}
