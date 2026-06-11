import React, { useState, useEffect } from 'react';
import { useHistory, useLocation } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';
import PageTitle from '@src/components/atoms/PageTitle';
import FBLoading from '@src/components/organisms/FBLoading';
import DeferredComponent from '@src/hooks/useDeferredComponent';
import { useTranslation } from 'react-i18next';

// CSV 테이블 렌더링 컴포넌트
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

  if (loading) {
    return <div style={{ padding: '10px', color: '#888', textAlign: 'center' }}>CSV Loading...</div>;
  }
  if (data.length === 0) {
    return <div style={{ padding: '10px', color: '#888', textAlign: 'center' }}>No CSV Data</div>;
  }

  const headers = data[0];
  const rows = data.slice(1);

  return (
    <div style={{ overflowX: 'auto', margin: '12px 0', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', minWidth: '600px' }}>
        <thead>
          <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: rowIndex % 2 === 0 ? '#ffffff' : '#f8fafc' }}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={{ padding: '8px 12px', color: '#334155' }}>
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

// 메인 평가 페이지
const SdsEvaluationPage = () => {
  const { t } = useTranslation();
  const history = useHistory();
  const location = useLocation();
  const wid = location.pathname.split('/')[3];
  const [selectedModel, setSelectedModel] = useState(null);
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evaluations, setEvaluations] = useState(() => {
    // LocalStorage에서 상태 복원
    const saved = localStorage.getItem('sds_evaluations');
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await callApi({
          url: 'services/sds-eval/samples',
          method: 'GET',
        });
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

  const completedCount = Object.keys(evaluations).filter(k => evaluations[k] !== null).length;
  const totalCount = 100; // 100개 항목

  // 결과 계산
  const oCount = Object.values(evaluations).filter(v => v === 'O').length;
  const xCount = Object.values(evaluations).filter(v => v === 'X').length;
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
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', fontFamily: 'Inter, system-ui, sans-serif' }}>
      
      {/* 고정 상단 헤더 */}
      <div style={{
        position: 'sticky',
        top: 0,
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid #e2e8f0',
        padding: '16px 24px',
        zIndex: 50,
        borderRadius: '12px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
        marginBottom: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <button 
              onClick={() => history.goBack()}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '14px',
                fontWeight: '500',
                padding: '0',
                marginBottom: '4px'
              }}
            >
              &larr; 뒤로가기
            </button>
            <PageTitle>SDS Expert Evaluation</PageTitle>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
              평가 완료: {completedCount} / {totalCount}
            </span>
          </div>
        </div>

        {/* 프로그레스 바 */}
        <div style={{ width: '100%', height: '8px', backgroundColor: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            width: `${(completedCount / totalCount) * 100}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #3b82f6 0%, #10b981 100%)',
            transition: 'width 0.3s ease-in-out'
          }} />
        </div>

        {/* 결과 패널 */}
        {isAllCompleted && (
          <div style={{
            marginTop: '8px',
            padding: '16px',
            backgroundColor: '#ecfdf5',
            border: '1px solid #a7f3d0',
            borderRadius: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            animation: 'fadeIn 0.5s ease-out'
          }}>
            <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
              <span style={{ fontSize: '16px', fontWeight: '700', color: '#065f46' }}>🎉 모든 평가 완료! 결과 분석:</span>
              <div style={{ display: 'flex', gap: '16px' }}>
                <span style={{ fontSize: '15px', color: '#065f46', fontWeight: '500' }}>
                  O (적합): <strong style={{ fontSize: '18px', color: '#10b981' }}>{oCount}개</strong> ({oPercent}%)
                </span>
                <span style={{ fontSize: '15px', color: '#065f46', fontWeight: '500' }}>
                  X (부적합): <strong style={{ fontSize: '18px', color: '#ef4444' }}>{xCount}개</strong> ({xPercent}%)
                </span>
              </div>
            </div>
            <button
              onClick={() => {
                if (window.confirm('평가 데이터를 초기화하시겠습니까?')) {
                  setEvaluations({});
                  localStorage.removeItem('sds_evaluations');
                }
              }}
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #d1fae5',
                color: '#065f46',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '13px',
                transition: 'background-color 0.2s'
              }}
            >
              초기화
            </button>
          </div>
        )}
      </div>

      {/* 평가 대상 모델 선택 */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#475569', marginBottom: '12px', borderLeft: '3px solid #3b82f6', paddingLeft: '10px' }}>
          평가 대상 모델
        </div>
        <ModelSelector
          wid={wid}
          selected={selectedModel}
          onSelect={(id) => setSelectedModel(id)}
        />
      </div>

      {/* 리스트 카드 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
        {samples.map((sample, index) => {
          const id = sample.id;
          const imageUrl = `/sds-dataset/${id}/input_image.png`;
          const csvUrl = `/sds-dataset/${id}/input_data.csv`;
          const inputText = sample.conversations && sample.conversations[0] 
            ? sample.conversations[0].value.replace(/<image>\n?/gi, '') 
            : '';
          const outputText = sample.conversations && sample.conversations[1] 
            ? sample.conversations[1].value 
            : '';
          const currentEval = evaluations[index] !== undefined ? evaluations[index] : null;

          return (
            <div 
              key={id} 
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '16px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.02), 0 2px 4px -1px rgba(0,0,0,0.02)',
                padding: '24px',
                transition: 'transform 0.2s, box-shadow 0.2s',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px'
              }}
            >
              {/* 카드 헤더 (샘플 인덱스 & ID) */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' }}>
                <span style={{ fontSize: '16px', fontWeight: '700', color: '#1e293b' }}>
                  Sample #{index + 1}
                </span>
                <span style={{ fontSize: '12px', color: '#94a3b8', fontFamily: 'monospace' }}>
                  ID: {id}
                </span>
              </div>

              {/* 1. 이미지 */}
              <div>
                <label style={{ fontSize: '13px', fontWeight: '600', color: '#64748b', display: 'block', marginBottom: '8px' }}>
                  1. Image
                </label>
                <div style={{
                  backgroundColor: '#f8fafc',
                  borderRadius: '10px',
                  border: '1px solid #f1f5f9',
                  overflow: 'hidden',
                  display: 'flex',
                  justifyContent: 'center',
                  maxHeight: '400px'
                }}>
                  <img 
                    src={imageUrl} 
                    alt={`Input ${id}`} 
                    style={{ maxWidth: '100%', objectFit: 'contain', maxHeight: '400px' }}
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                </div>
              </div>

              {/* 2. CSV 데이터 테이블 */}
              <div>
                <label style={{ fontSize: '13px', fontWeight: '600', color: '#64748b', display: 'block', marginBottom: '8px' }}>
                  2. CSV Data (input_data.csv)
                </label>
                <CsvTable url={csvUrl} />
              </div>

              {/* 3. 입력 텍스트 */}
              <div>
                <label style={{ fontSize: '13px', fontWeight: '600', color: '#64748b', display: 'block', marginBottom: '6px' }}>
                  3. Input Text
                </label>
                <div style={{
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  color: '#334155',
                  whiteSpace: 'pre-wrap'
                }}>
                  {inputText}
                </div>
              </div>

              {/* 4. 출력 텍스트 */}
              <div>
                <label style={{ fontSize: '13px', fontWeight: '600', color: '#64748b', display: 'block', marginBottom: '6px' }}>
                  4. Output Advice (Model response)
                </label>
                <div style={{
                  backgroundColor: '#f0f9ff',
                  border: '1px solid #bae6fd',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  color: '#0369a1',
                  whiteSpace: 'pre-wrap'
                }}>
                  {outputText}
                </div>
              </div>

              {/* 5. 전문가 평가 */}
              <div style={{
                marginTop: '12px',
                paddingTop: '16px',
                borderTop: '1px solid #f1f5f9',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: '#475569' }}>
                  5. 전문가 평가 (Expert Evaluation)
                </span>
                
                <div style={{ display: 'flex', gap: '16px' }}>
                  {/* O 버튼 */}
                  <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1px solid',
                    borderColor: currentEval === 'O' ? '#10b981' : '#cbd5e1',
                    backgroundColor: currentEval === 'O' ? '#ecfdf5' : '#ffffff',
                    color: currentEval === 'O' ? '#047857' : '#475569',
                    fontWeight: '600',
                    transition: 'all 0.2s',
                    userSelect: 'none'
                  }}>
                    <input 
                      type="radio" 
                      name={`eval-${index}`} 
                      value="O" 
                      checked={currentEval === 'O'}
                      onChange={() => handleEvaluate(index, 'O')}
                      style={{ accentColor: '#10b981', cursor: 'pointer' }}
                    />
                    적합 (O)
                  </label>

                  {/* X 버튼 */}
                  <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1px solid',
                    borderColor: currentEval === 'X' ? '#ef4444' : '#cbd5e1',
                    backgroundColor: currentEval === 'X' ? '#fef2f2' : '#ffffff',
                    color: currentEval === 'X' ? '#b91c1c' : '#475569',
                    fontWeight: '600',
                    transition: 'all 0.2s',
                    userSelect: 'none'
                  }}>
                    <input 
                      type="radio" 
                      name={`eval-${index}`} 
                      value="X" 
                      checked={currentEval === 'X'}
                      onChange={() => handleEvaluate(index, 'X')}
                      style={{ accentColor: '#ef4444', cursor: 'pointer' }}
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
