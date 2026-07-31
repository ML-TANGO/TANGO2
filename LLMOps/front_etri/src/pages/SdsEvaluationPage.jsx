import React, { useState, useEffect } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import { callApi, STATUS_SUCCESS } from '@src/network';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import PageTitle from '@src/components/atoms/PageTitle';
import FBLoading from '@src/components/organisms/FBLoading';
import DeferredComponent from '@src/hooks/useDeferredComponent';
import { useTranslation } from 'react-i18next';
import { convertBinaryByte } from '@src/utils';
import { convertLocalTime } from '@src/datetimeUtils';
import style from './SdsEvaluationPage.module.scss';

const cx = classNames.bind(style);

const CsvTable = ({ url }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error('Network response was not ok');
        return res.text();
      })
      .then((text) => {
        const rows = text.split('\n').filter((row) => row.trim() !== '');
        const parsed = rows.map((row) => row.split(','));
        setData(parsed);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching CSV:', err);
        setLoading(false);
      });
  }, [url]);

  if (loading) return <div className={cx('csv-status')}>CSV Loading...</div>;
  if (data.length === 0) return <div className={cx('csv-status')}>No CSV Data</div>;

  const headers = data[0];
  const rows = data.slice(1);

  return (
    <div className={cx('csv-wrap')}>
      <table className={cx('csv-table')}>
        <thead className={cx('csv-thead')}>
          <tr>
            {headers.map((h, i) => (
              <th key={i} className={cx('csv-th')}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className={cx(rowIndex % 2 === 0 ? 'csv-tr-even' : 'csv-tr-odd')}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className={cx('csv-td')}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const SdsEvaluationPage = () => {
  const { t } = useTranslation();
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];
  const [selectedModel, setSelectedModel] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evaluations, setEvaluations] = useState(() => {
    const saved = localStorage.getItem('sds_evaluations');
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [samplesRes, datasetsRes] = await Promise.all([
          callApi({ url: 'services/sds-eval/samples', method: 'GET' }),
          callApi({ url: `datasets?workspace_id=${wid}`, method: 'GET' }),
        ]);
        if (samplesRes.status === STATUS_SUCCESS) setSamples(samplesRes.result || []);
        if (datasetsRes.status === STATUS_SUCCESS) setDatasets(datasetsRes.result?.list || []);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [wid]);

  const handleEvaluate = (index, value) => {
    const nextEval = { ...evaluations, [index]: value };
    setEvaluations(nextEval);
    localStorage.setItem('sds_evaluations', JSON.stringify(nextEval));
  };

  const completedCount = Object.keys(evaluations).filter((k) => evaluations[k] !== null).length;
  const totalCount = 100;
  const oCount = Object.values(evaluations).filter((v) => v === 'O').length;
  const xCount = Object.values(evaluations).filter((v) => v === 'X').length;
  const oPercent = completedCount > 0 ? ((oCount / completedCount) * 100).toFixed(1) : 0;
  const xPercent = completedCount > 0 ? ((xCount / completedCount) * 100).toFixed(1) : 0;
  const isAllCompleted = completedCount === totalCount;

  if (loading) {
    return (
      <div className={cx('loading-center')}>
        <DeferredComponent>
          <FBLoading />
        </DeferredComponent>
      </div>
    );
  }

  return (
    <div className={cx('page')}>
      <div className={cx('sticky-header')}>
        <div className={cx('header-row')}>
          <div>
            <button className={cx('back-btn')} onClick={() => history.goBack()}>
              &larr; 뒤로가기
            </button>
            <PageTitle>SDS Expert Evaluation</PageTitle>
          </div>
          <span className={cx('progress-count')}>
            평가 완료: {completedCount} / {totalCount}
          </span>
        </div>

        <div className={cx('progress-bar')}>
          <div
            className={cx('progress-fill')}
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        </div>

        {isAllCompleted && (
          <div className={cx('complete-banner')}>
            <div className={cx('complete-stats')}>
              <span className={cx('complete-title')}>🎉 모든 평가 완료! 결과 분석:</span>
              <span>
                O (적합): <strong className={cx('stat-o')}>{oCount}개</strong> ({oPercent}%)
              </span>
              <span>
                X (부적합): <strong className={cx('stat-x')}>{xCount}개</strong> ({xPercent}%)
              </span>
            </div>
            <button
              className={cx('reset-btn')}
              onClick={() => {
                if (window.confirm('평가 데이터를 초기화하시겠습니까?')) {
                  setEvaluations({});
                  localStorage.removeItem('sds_evaluations');
                }
              }}
            >
              초기화
            </button>
          </div>
        )}
      </div>

      <div className={cx('model-section')}>
        <div className={cx('section-label')}>평가 대상 모델</div>
        <ModelSelector wid={wid} selected={selectedModel} onSelect={(id) => { setSelectedModel(id); setSelectedDataset(null); }} />
      </div>

      {selectedModel && (
        <div className={cx('dataset-section')}>
          <div className={cx('ds-section-header')}>
            <span className={cx('ds-section-title')}>평가 데이터셋</span>
            <span className={cx('ds-count-badge')}>{datasets.length}개</span>
            <div className={cx('ds-spacer')} />
            {selectedDataset && (
              <span className={cx('ds-selected-label')}>
                선택됨: <strong>{selectedDataset.dataset_name}</strong>
              </span>
            )}
          </div>

          <div className={cx('ds-toolbar')}>
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
          </div>

          {datasets.filter((d) => d.dataset_name.includes(datasetKeyword)).length === 0 ? (
            <div className={cx('ds-empty')}>등록된 데이터셋이 없습니다.</div>
          ) : (
            <div className={cx('ds-list')}>
              {datasets
                .filter((d) => d.dataset_name.includes(datasetKeyword))
                .map((item) => {
                  const isSelected = selectedDataset?.id === item.id;
                  return (
                    <div
                      key={item.id}
                      className={cx('ds-card', isSelected && 'ds-card--on')}
                      onClick={() => setSelectedDataset(isSelected ? null : item)}
                    >
                      <div className={cx('ds-check', isSelected && 'ds-check--on')}>
                        {isSelected && '✓'}
                      </div>
                      <div className={cx('ds-card-body')}>
                        <div className={cx('ds-card-name-row')}>
                          <span className={cx('ds-card-name')}>{item.dataset_name}</span>
                          {item.format && (
                            <span className={cx('ds-format-badge')}>{item.format}</span>
                          )}
                          <span className={cx('ds-access-badge', Number(item.access) === 0 ? 'ds-access--ro' : 'ds-access--rw')}>
                            {Number(item.access) === 0 ? '읽기전용' : '읽기/쓰기'}
                          </span>
                        </div>
                        <div className={cx('ds-card-meta')}>
                          {item.owner && <span>{item.owner}</span>}
                          {item.owner && <span className={cx('dot')}>·</span>}
                          <span>{item.size ? convertBinaryByte(item.size) : '0 Bytes'}</span>
                          {item.file_count != null && (
                            <>
                              <span className={cx('dot')}>·</span>
                              <span>{item.file_count.toLocaleString()}개 파일</span>
                            </>
                          )}
                          {item.create_datetime && (
                            <>
                              <span className={cx('dot')}>·</span>
                              <span>{convertLocalTime(item.create_datetime)}</span>
                            </>
                          )}
                        </div>
                        {item.description && (
                          <div className={cx('ds-card-desc')}>{item.description}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      )}

      <div className={cx('sample-list')} style={{ display: selectedDataset ? undefined : 'none' }}>
        {samples.map((sample, index) => {
          const id = sample.id;
          const imageUrl = `/sds-dataset/${id}/input_image.png`;
          const csvUrl = `/sds-dataset/${id}/input_data.csv`;
          const inputText =
            sample.conversations && sample.conversations[0]
              ? sample.conversations[0].value.replace(/<image>\n?/gi, '')
              : '';
          const outputText =
            sample.conversations && sample.conversations[1]
              ? sample.conversations[1].value
              : '';
          const currentEval = evaluations[index] !== undefined ? evaluations[index] : null;

          return (
            <div key={id} className={cx('sample-card')}>
              <div className={cx('card-header')}>
                <span className={cx('sample-num')}>Sample #{index + 1}</span>
                <span className={cx('sample-id')}>ID: {id}</span>
              </div>

              <div className={cx('field-group')}>
                <label className={cx('field-label')}>1. Image</label>
                <div className={cx('image-container')}>
                  <img
                    src={imageUrl}
                    alt={`Input ${id}`}
                    className={cx('sample-img')}
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                </div>
              </div>

              <div className={cx('field-group')}>
                <label className={cx('field-label')}>2. CSV Data (input_data.csv)</label>
                <CsvTable url={csvUrl} />
              </div>

              <div className={cx('field-group')}>
                <label className={cx('field-label')}>3. Input Text</label>
                <div className={cx('text-block')}>{inputText}</div>
              </div>

              <div className={cx('field-group')}>
                <label className={cx('field-label')}>4. Output Advice (Model response)</label>
                <div className={cx('output-block')}>{outputText}</div>
              </div>

              <div className={cx('eval-row')}>
                <span className={cx('eval-title')}>5. 전문가 평가 (Expert Evaluation)</span>
                <div className={cx('eval-btns')}>
                  <label className={cx('eval-btn', currentEval === 'O' && 'active-o')}>
                    <input
                      type="radio"
                      name={`eval-${index}`}
                      value="O"
                      checked={currentEval === 'O'}
                      onChange={() => handleEvaluate(index, 'O')}
                      className={cx('eval-radio')}
                    />
                    적합 (O)
                  </label>
                  <label className={cx('eval-btn', currentEval === 'X' && 'active-x')}>
                    <input
                      type="radio"
                      name={`eval-${index}`}
                      value="X"
                      checked={currentEval === 'X'}
                      onChange={() => handleEvaluate(index, 'X')}
                      className={cx('eval-radio')}
                    />
                    부적합 (X)
                  </label>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SdsEvaluationPage;
