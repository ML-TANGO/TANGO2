import { useState } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import style from './BenchmarkEvaluationPage.module.scss';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

const cx = classNames.bind(style);

const DATASETS = [
  { id: 'mixatis',      label: 'MixATIS',      desc: '다중 의도 슬롯 채움 벤치마크',         format: 'JSON' },
  { id: 'logickor',     label: 'LogicKor',      desc: '한국어 추론 능력 평가 데이터셋',         format: 'JSONL' },
  { id: 'obj_detect',   label: '객체탐지',      desc: 'COCO 기반 객체 탐지 평가',              format: 'JSON' },
  { id: 'segmentation', label: '세그멘테이션',  desc: '픽셀 단위 분할 정확도 평가',             format: 'JSON' },
  { id: 'ocr',          label: 'OCR',           desc: '문자 인식 정확도 평가',                  format: 'CSV' },
];

const METRICS = [
  { id: 'accuracy',   label: 'Accuracy',   desc: '전체 정답률' },
  { id: 'f1',         label: 'F1 Score',   desc: 'Precision과 Recall의 조화평균' },
  { id: 'acc_norm',   label: 'ACC_NORM',   desc: '정규화된 정확도' },
  { id: 'arc',        label: 'ARC',        desc: 'AI2 Reasoning Challenge' },
  { id: 'kobest',     label: 'KoBEST',     desc: '한국어 NLU 벤치마크' },
  { id: 'mmlu',       label: 'MMLU',       desc: '다분야 언어 이해 (57개 과목)' },
  { id: 'hellaswag',  label: 'HellaSwag',  desc: '상식 추론 — 문장 완성' },
  { id: 'winogrande', label: 'WinoGrande', desc: '상식 추론 — 대명사 해소' },
  { id: 'gsm8k',      label: 'GSM8K',      desc: '초등 수학 문제 풀기' },
  { id: 'truthfulqa', label: 'TruthfulQA', desc: '사실 정확성 평가' },
  { id: 'boolq',      label: 'BoolQ',      desc: '예/아니오 질의응답' },
  { id: 'humaneval',  label: 'HumanEval',  desc: '코드 생성 능력 평가' },
  { id: 'meteor',     label: 'METEOR',     desc: '번역/생성 품질 — 단어 정렬 기반' },
  { id: 'cider',      label: 'CIDEr',      desc: '이미지 캡셔닝 품질 — TF-IDF 가중치' },
  { id: 'spice',      label: 'SPICE',      desc: '장면 그래프 기반 의미 유사도' },
  { id: 'bleu',       label: 'BLEU',       desc: 'N-gram 정밀도 기반 번역 품질' },
  { id: 'rouge',      label: 'ROUGE-L',    desc: '최장 공통 부분 수열 기반 요약 품질' },
];

export default function BenchmarkEvaluationPage() {
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];

  const [selectedModel, setSelectedModel] = useState(null);
  const [selectedDatasets, setSelectedDatasets] = useState([]);
  const [selectedMetrics, setSelectedMetrics] = useState([]);
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  const toggleDataset = (id) =>
    setSelectedDatasets((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const toggleMetric = (id) =>
    setSelectedMetrics((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const canRun = !!selectedModel && selectedDatasets.length > 0 && selectedMetrics.length > 0;

  const handleRun = () => {
    if (!canRun) return;
    setRunning(true);
    setResults(null);
    setTimeout(() => {
      const raw = selectedDatasets.flatMap((dsId) =>
        selectedMetrics.map((mtId) => ({
          datasetId: dsId,
          datasetLabel: DATASETS.find((d) => d.id === dsId)?.label,
          metricId: mtId,
          metricLabel: METRICS.find((m) => m.id === mtId)?.label,
          score: parseFloat((Math.random() * 38 + 52).toFixed(1)),
        }))
      );

      const metricAverages = selectedMetrics
        .map((mtId) => {
          const scores = raw.filter((r) => r.metricId === mtId).map((r) => r.score);
          const avg = parseFloat((scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1));
          return { metricId: mtId, label: METRICS.find((m) => m.id === mtId)?.label, avg };
        })
        .sort((a, b) => b.avg - a.avg);

      setResults({ raw, metricAverages });
      setRunning(false);
    }, 3000);
  };

  const filteredDatasets = DATASETS.filter((d) => d.label.includes(datasetKeyword) || d.desc.includes(datasetKeyword));

  return (
    <div className={cx('page')}>
      <div className={cx('header')}>
        <button className={cx('back-btn')} onClick={() => history.push(`/user/workspace/${wid}/services`)}>
          ← 목록으로
        </button>
        <h1 className={cx('title')}>벤치마크 평가</h1>
      </div>

      <div className={cx('body')}>
        {/* 평가 대상 모델 */}
        <section className={cx('section')}>
          <h2 className={cx('section-title')}>평가 대상 모델</h2>
          <ModelSelector wid={wid} selected={selectedModel} onSelect={(id) => setSelectedModel(id)} />
        </section>

        {/* 데이터셋 선택 — ds-card 리스트 */}
        <section className={cx('section')}>
          <div className={cx('ds-section-header')}>
            <h2 className={cx('section-title')}>데이터셋 선택</h2>
            <span className={cx('ds-count-badge')}>{DATASETS.length}개</span>
            <div className={cx('ds-spacer')} />
            {selectedDatasets.length > 0 && (
              <span className={cx('ds-selected-label')}>
                <strong>{selectedDatasets.length}개</strong> 선택됨
              </span>
            )}
          </div>

          <div className={cx('ds-search-wrap')}>
            <input
              className={cx('ds-search-input')}
              placeholder="데이터셋 이름 검색..."
              value={datasetKeyword}
              onChange={(e) => setDatasetKeyword(e.target.value)}
            />
            {datasetKeyword && (
              <button className={cx('ds-search-clear')} onClick={() => setDatasetKeyword('')}>✕</button>
            )}
          </div>

          {filteredDatasets.length === 0 ? (
            <div className={cx('ds-empty')}>해당하는 데이터셋이 없습니다.</div>
          ) : (
            <div className={cx('ds-list')}>
              {filteredDatasets.map((item) => {
                const isSel = selectedDatasets.includes(item.id);
                return (
                  <div
                    key={item.id}
                    className={cx('ds-card', isSel && 'ds-card--on')}
                    onClick={() => toggleDataset(item.id)}
                  >
                    <div className={cx('ds-check', isSel && 'ds-check--on')}>{isSel && '✓'}</div>
                    <div className={cx('ds-card-body')}>
                      <div className={cx('ds-card-name-row')}>
                        <span className={cx('ds-card-name')}>{item.label}</span>
                        {item.format && <span className={cx('ds-format-badge')}>{item.format}</span>}
                      </div>
                      <div className={cx('ds-card-desc')}>{item.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* 평가 메트릭 선택 */}
        <section className={cx('section')}>
          <div className={cx('ds-section-header')}>
            <h2 className={cx('section-title')}>평가 메트릭 선택</h2>
            {selectedMetrics.length > 0 && (
              <span className={cx('ds-count-badge')}>{selectedMetrics.length}개 선택됨</span>
            )}
          </div>
          <div className={cx('option-grid')}>
            {METRICS.map((m) => (
              <div
                key={m.id}
                className={cx('option-card', selectedMetrics.includes(m.id) && 'selected')}
                onClick={() => toggleMetric(m.id)}
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
          <>
            {/* 1. 메트릭별 점수 (정렬) */}
            <section className={cx('section')}>
              <h2 className={cx('section-title')}>메트릭 점수 요약 (높은 순)</h2>
              <div className={cx('score-grid')}>
                {results.metricAverages.map((m, i) => (
                  <div key={m.metricId} className={cx('score-card')}>
                    <div className={cx('score-rank')}>#{i + 1}</div>
                    <div className={cx('score-metric')}>{m.label}</div>
                    <div className={cx('score-value')}>{m.avg.toFixed(1)}%</div>
                  </div>
                ))}
              </div>
            </section>

            {/* 2. 막대 그래프 */}
            <section className={cx('section')}>
              <h2 className={cx('section-title')}>메트릭 점수 차트</h2>
              <div className={cx('chart-wrap')}>
                {results.metricAverages.map((m) => (
                  <div key={m.metricId} className={cx('chart-row')}>
                    <div className={cx('chart-label')}>{m.label}</div>
                    <div className={cx('chart-bar-wrap')}>
                      <div
                        className={cx('chart-bar')}
                        style={{ width: `${m.avg}%` }}
                      />
                    </div>
                    <div className={cx('chart-value')}>{m.avg.toFixed(1)}%</div>
                  </div>
                ))}
              </div>
            </section>

            {/* 3. 메트릭(태스크)별 상세 결과 테이블 */}
            <section className={cx('section')}>
              <h2 className={cx('section-title')}>태스크별 상세 결과</h2>
              <div className={cx('table-wrap')}>
                <table className={cx('result-table')}>
                  <thead>
                    <tr>
                      <th>메트릭 (태스크)</th>
                      {selectedDatasets.map((dsId) => (
                        <th key={dsId}>{DATASETS.find((d) => d.id === dsId)?.label}</th>
                      ))}
                      <th>평균</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.metricAverages.map((m) => (
                      <tr key={m.metricId}>
                        <td className={cx('metric-cell')}>{m.label}</td>
                        {selectedDatasets.map((dsId) => {
                          const cell = results.raw.find(
                            (r) => r.metricId === m.metricId && r.datasetId === dsId
                          );
                          return (
                            <td key={dsId} className={cx('score')}>
                              {cell ? `${cell.score.toFixed(1)}%` : '–'}
                            </td>
                          );
                        })}
                        <td className={cx('score', 'avg')}>{m.avg.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
