import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';

import '@src/styles/font.scss';

const TableBarTooltip = ({ usedData, remainingData, t }) => {
  const [hoveredSection, setHoveredSection] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [barWidth, setBarWidth] = useState(0); // 현재 progress bar의 너비 저장
  const progressBarRef = useRef();
  const progress = usedData?.pcent || 100 - remainingData?.pcent; // 사용된 용량 비율 .. 우선 parse된 값을 받아오는 것으로

  useEffect(() => {
    // Progress bar width 업뎃
    const updateBarWidth = () => {
      if (progressBarRef.current) {
        setBarWidth(progressBarRef.current.getBoundingClientRect().width);
      }
    };

    updateBarWidth();

    // 윈도우 리사이즈 시 너비 업뎃
    window.addEventListener('resize', updateBarWidth);
    return () => {
      window.removeEventListener('resize', updateBarWidth);
    };
  }, []);

  const handleMouseEnter = (section, event) => {
    const progressBarRect = progressBarRef.current.getBoundingClientRect();
    const mouseY = progressBarRect.top - 10;

    // 각 섹션의 중앙 위치 계산
    const sectionWidth =
      section === 'used'
        ? barWidth * (progress / 100)
        : barWidth * ((100 - progress) / 100);
    const sectionStart =
      section === 'used'
        ? progressBarRect.left
        : progressBarRect.left + barWidth * (progress / 100);
    const sectionCenter = sectionStart + sectionWidth / 2;

    setTooltipPosition({
      top: mouseY,
      left: sectionCenter,
    });

    setHoveredSection(section);
  };

  const handleMouseLeave = () => {
    setHoveredSection(null);
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      }}
    >
      {/* Progress Bar */}
      <div
        ref={progressBarRef}
        style={{
          position: 'relative',
          width: '80%',
          height: '8px',
          border: '1px solid #DBDBDB',
          display: 'flex',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        {/* 왼쪽(사용된 부분) */}
        <div
          style={{
            width: `${Math.min(progress, 100)}%`,
            backgroundColor: '#2D76F8', // used % 색깔
            height: '100%',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => handleMouseEnter('used', e)}
          onMouseLeave={handleMouseLeave}
        ></div>
        {/* 오른쪽(남은 부분) */}
        <div
          style={{
            width: `${100 - Math.min(progress, 100)}%`, // 남은 부분
            backgroundColor: '#fff',
            height: '100%',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => handleMouseEnter('remaining', e)}
          onMouseLeave={handleMouseLeave}
        ></div>
      </div>

      {/* 퍼센트 텍스트 표시 */}
      <div
        style={{
          fontWeight: 'bold',
          color: '#121619',
          fontSize: '14px',
          width: '30px',
          whiteSpace: 'nowrap',
        }}
      >
        {progress}%
      </div>

      {/* 포탈을 이용한 툴팁 */}
      {hoveredSection &&
        ReactDOM.createPortal(
          <div
            style={{
              position: 'absolute',
              top: `${tooltipPosition.top}px`,
              left: `${tooltipPosition.left}px`,
              backgroundColor:
                hoveredSection === 'used' ? '#042659' : '#042659',
              color: 'white',
              padding: '12px',
              borderRadius: '4px',
              fontSize: '12px',
              pointerEvents: 'none',
              transform: 'translate(-50%, -100%)',
              whiteSpace: 'nowrap',
              transition: 'opacity 0.3s ease, transform 0.3s ease',
              visibility: hoveredSection ? 'visible' : 'hidden',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              minWidth: '100px',
            }}
          >
            {(hoveredSection === 'used' && usedData?.pcent) ||
            (hoveredSection === 'remaining' && remainingData?.pcent) ? (
              <div
                style={{
                  marginBottom: '8px',
                  textAlign: 'left',
                  width: '100%',
                  paddingBottom: '8px',
                  fontFamily: 'SpoqaM',
                  borderBottom: '1px solid #FFF',
                  fontSize: '12px',
                }}
              >
                <span style={{ marginRight: '8px' }}>
                  {t('availableCapacity.label')}
                </span>
                {hoveredSection === 'used'
                  ? usedData.pcent
                  : remainingData.pcent}
                %
              </div>
            ) : null}

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                alignItems: 'flex-start',
                fontSize: '10px',
                fontFamily: 'SpoqaM',
              }}
            >
              {/* 각 데이터 표시 */}
              <div
                style={{ width: '100%', textAlign: 'left', display: 'flex' }}
              >
                <div
                  style={{ width: '42px', flexBasis: '42px', flexShrink: 0 }}
                >
                  vGPU:
                </div>
                <span style={{ marginRight: '8px', fontFamily: 'SpoqaB' }}>
                  {hoveredSection === 'used'
                    ? usedData.gpu ?? '-'
                    : remainingData.gpu ?? '-'}
                </span>
                EA
              </div>
              <div
                style={{ width: '100%', textAlign: 'left', display: 'flex' }}
              >
                <div
                  style={{ width: '42px', flexBasis: '42px', flexShrink: 0 }}
                >
                  vCPU:
                </div>
                <span style={{ marginRight: '8px', fontFamily: 'SpoqaB' }}>
                  {hoveredSection === 'used'
                    ? usedData.cpu ?? '-'
                    : remainingData.cpu ?? '-'}
                </span>
                Cores
              </div>
              <div
                style={{ width: '100%', textAlign: 'left', display: 'flex' }}
              >
                <div
                  style={{ width: '42px', flexBasis: '42px', flexShrink: 0 }}
                >
                  RAM:
                </div>
                <span style={{ marginRight: '8px', fontFamily: 'SpoqaB' }}>
                  {hoveredSection === 'used'
                    ? usedData.ram ?? '-'
                    : remainingData.ram ?? '-'}
                </span>
                GB
              </div>
            </div>
            <div
              style={{
                content: '""',
                position: 'absolute',
                bottom: '-8px',
                left: '50%',
                marginLeft: '-5px',
                width: 0,
                height: 0,
                borderTop: `8px solid ${
                  hoveredSection === 'used' ? '#042659' : '#042659'
                }`,
                borderLeft: '5px solid transparent',
                borderRight: '5px solid transparent',
              }}
            />
          </div>,
          document.body,
        )}
    </div>
  );
};

export default TableBarTooltip;
