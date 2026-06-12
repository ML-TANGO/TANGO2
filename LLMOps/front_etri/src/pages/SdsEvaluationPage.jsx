import React, { useState, useEffect } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import classNames from 'classnames/bind';
import { callApi, STATUS_SUCCESS } from '@src/network';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import PageTitle from '@src/components/atoms/PageTitle';
import FBLoading from '@src/components/organisms/FBLoading';
import DeferredComponent from '@src/hooks/useDeferredComponent';
import { useTranslation } from 'react-i18next';
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

  if (loading) return <div style={{ padding: '10px', color: '#888', textAlign: 'center' }}>CSV Loading...</div>;
  if (data.length === 0) return <div style={{ padding: '10px', color: '#888', textAlign: 'center' }}>No CSV Data</div>;

  const headers = data[0];
  const rows = data.slice(1);

  return (
    <div style={{ overflowX: 'auto', margin: '12px 0', borderRadius: '6px', border: '1px solid #dbdbdb' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', minWidth: '600px' }}>
        <thead>
          <tr style={{ backgroundColor: '#f0f0f0', borderBottom: '2px solid #dbdbdb' }}>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: '600', color: '#747474' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} style={{ borderBottom: '1px solid #f0f0f0', backgroundColor: rowIndex % 2 === 0 ? '#ffffff' : '#f0f0f0' }}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={{ padding: '8px 12px', color: '#121619' }}>
                  {cell}
                </td>
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
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evaluations, setEvaluations] = useState(() => {
    const saved = localStorage.getItem('sds_evaluations');
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await callApi({ url: 'services/sds-eval/samples', method: 'GET' });
        if (response.status === STATUS_SUCCESS) {
          setSamples(response.result || []);
        } else {
          console.error('Failed to load samples:', response.message);
        }
      } catch (error) {
        console.error('Error fetching samples:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

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
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
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
        <ModelSelector wid={wid} selected={selectedModel} onSelect={(id) => setSelectedModel(id)} />
      </div>

      <div className={cx('sample-list')}>
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
                    style={{ maxWidth: '100%', objectFit: 'contain', maxHeight: '400px' }}
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
                      style={{ cursor: 'pointer' }}
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
                      style={{ cursor: 'pointer' }}
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
