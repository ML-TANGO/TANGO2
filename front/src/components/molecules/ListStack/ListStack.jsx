import React, { useLayoutEffect, useRef, useState } from 'react';

import PartStack from './PartStack';

import classNames from 'classnames/bind';
import style from './ListStack.module.scss';

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

const ListStack = ({
  isTooltip,
  tooltipDirection,
  stackList,
  totalValue,
  ...rest
}) => {
  const stackContRef = useRef(null);
  const [widthList, setWidthList] = useState([]);

  useLayoutEffect(() => {
    if (stackContRef.current) {
      const widthList = stackList.map((stackInfo) => {
        const { value } = stackInfo;
        const width = calWidth(value, totalValue, stackContRef);
        return Math.floor(width - 2);
      });
      setWidthList(widthList);
    }
  }, [stackList, totalValue]);

  return (
    <div className={cx('stack-cont-inner')} ref={stackContRef} {...rest}>
      {stackContRef.current &&
        stackList.map((stackInfo, idx) => {
          const { tooltipContent } = stackInfo;
          return (
            <PartStack
              key={idx}
              idx={idx}
              isTooltip={isTooltip}
              tooltipDirection={tooltipDirection}
              tooltipContent={tooltipContent}
              width={widthList[idx]}
              color={stackInfo.color}
            />
          );
        })}
    </div>
  );
};

export default ListStack;
