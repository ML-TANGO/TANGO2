import React, { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import { convertBinaryByte } from '@src/utils';

import PartStack from './PartStack';

import classNames from 'classnames/bind';
import style from './ResourceStack.module.scss';

const cx = classNames.bind(style);

export const BAR_COLOR = [
  '#DEE9FF',
  '#C8DBFD',
  '#93BAFF',
  '#2D76F8',
  '#164ABE',
  '#002F77',
  '#042659',
  '#C1C1C1',
  '#747474',
  '#3E3E3E',
  '#7E7E7F',
  '#FFF8D9',
  '#FFE6B0',
  '#FFD488',
  '#FFC260',
  '#FFB038',
  '#FF9E10',
  '#FF7A00',
  '#E3FCEE',
  '#C3F2D5',
  '#A3E8BC',
  '#83DFA3',
  '#63D58A',
  '#00C775',
  '#00C775',
];

const calWidth = (value, total, stackContRef) => {
  if (!stackContRef.current) return 0;
  const stackContRect = stackContRef.current.getBoundingClientRect();
  const percentage = value / total;
  const width = stackContRect.width * percentage;
  return width;
};

const ResourceStack = ({
  stackList,
  totalValue,
  type,
  remaining,
  unit,
  test,
}) => {
  const { t } = useTranslation();
  const stackContRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);
  const [emptyWidth, setEmptyWidth] = useState(0);

  const emptyStackRef = useRef(null);

  useEffect(() => {
    if (stackContRef.current) {
      let filledWidth = stackList.reduce(
        (acc, { used }) => acc + calWidth(used, totalValue, stackContRef),
        0,
      );

      // if (test === 'gpu') {
      // console.log('-----------------');
      // console.log('1', filledWidth);
      // console.log('2', stackList);
      // console.log('3', totalValue);
      // console.log('-----------------');
      // }

      setEmptyWidth(
        stackContRef.current.getBoundingClientRect().width - filledWidth,
      );
    }
  }, [stackList, totalValue]);

  return (
    <div className={cx('stack-cont')} ref={stackContRef}>
      {stackList.map((stackInfo, idx) => {
        const { name, used, pcent } = stackInfo;
        const width = calWidth(used, totalValue, stackContRef);
        // count 숫자 몇번째인지
        // totalvlue 총 몇개
        return (
          <PartStack
            key={`${idx}-${name}-${used}`}
            idx={idx}
            stackInfo={stackInfo}
            width={width}
            type={type}
            pcent={pcent}
            unit={unit}
          />
        );
      })}

      {/* 남은 하얀색 부분 */}
      {emptyWidth > 0 && (
        <div
          ref={emptyStackRef}
          className={cx('empty-stack')}
          style={{ width: `${emptyWidth}px` }}
          onMouseEnter={() => setIsShowTooltip(true)}
          onMouseLeave={() => setIsShowTooltip(false)}
        />
      )}

      <TooltipPortal
        direction='top'
        targetRef={emptyStackRef}
        isShowTooltip={isShowTooltip}
      >
        <DarkTooltip
          direction='top'
          content={
            <div
              style={{
                display: 'flex',
                gap: '8px',
                fontFamily: 'SpoqaB',
                fontSize: '10px',
              }}
            >
              <div>
                <span style={{ marginRight: '12px' }}>
                  {t('availableCapacity.label')}
                </span>
                <span>
                  {unit === 'GB' ? (
                    convertBinaryByte(remaining ?? 0)
                  ) : (
                    <>
                      {remaining ?? '-'}
                      <span style={{ marginLeft: '6px' }}>{unit}</span>
                    </>
                  )}
                </span>
              </div>
            </div>
          }
        />
      </TooltipPortal>
    </div>
  );
};

// ---- 아래 데이터 백엔드에 요청. 안 들어있음 ...흐 -
// ? cpu 할당 쪽 퍼센트 (툴팁했을때 나오는 ), 할당 값

// ? gpu 할당 쪽 퍼센트, 할당 값값

// ? ram 할당 쪽 값, 할당 쪽 퍼센트. 없음 (지금 used랑 used_usage만 오고있어)

// ? storage 일단 워크스페이스 합쳐주시고 매니저이름, 할당 퍼센트, 사용 퍼센트

// ? 잔여량 string으로 다 받고
export default ResourceStack;
