import React, { useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

// CSS Module
import classNames from 'classnames/bind';
import style from './DatasetComTable.module.scss';

const cx = classNames.bind(style);

const TableLine = ({ idx, type, input, output, time }) => {
  const inputContent = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  return (
    <>
      <div
        className={cx(
          'tr',
          idx % 2 === 1 && 'purple',
          type === 'input' && 'one-grid',
        )}
        ref={inputContent}
        onMouseEnter={() => setIsShowTooltip(true)}
        onMouseLeave={() => setIsShowTooltip(false)}
        key={idx}
      >
        <div className={cx('td')}>{input}</div>
        {type !== 'input' && (
          <>
            <div className={cx('td')}>{output}</div>
            <div className={cx('td')}>{time}</div>
          </>
        )}
      </div>
      <TooltipPortal
        direction='bottom'
        targetRef={inputContent}
        isShowTooltip={isShowTooltip}
      >
        <DarkTooltip
          direction='bottom'
          content={
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                width: '240px',
                fontFamily: 'SpoqaM',
                fontSize: '10px',
                justifyContent: 'center',
              }}
            >
              <p
                style={{
                  wordBreak: 'break-word',
                  overflowWrap: 'break-word',
                  whiteSpace: 'normal',
                }}
              >
                입력 내용: {input}
              </p>
              {type !== 'input' && (
                <>
                  <p
                    style={{
                      wordBreak: 'break-word',
                      overflowWrap: 'break-word',
                      whiteSpace: 'normal',
                    }}
                  >
                    출력 내용: {output}
                  </p>
                  <p
                    style={{
                      wordBreak: 'break-word',
                      overflowWrap: 'break-word',
                      whiteSpace: 'normal',
                    }}
                  >
                    응답 시간: {time}
                  </p>
                </>
              )}
            </div>
          }
        />
      </TooltipPortal>
    </>
  );
};

export default function DatasetComTable({ type, list = [] }) {
  return (
    <>
      {!!list.length && (
        <div className={cx('input-table')}>
          <div className={cx('thead')}>
            <div className={cx('tr')}>
              <div className={cx('th')}>입력 내용</div>
              {type !== 'input' && (
                <>
                  <div className={cx('th')}>출력 내용</div>
                  <div className={cx('th')}>응답 시간</div>
                </>
              )}
            </div>
          </div>
          <div className={cx('tbody')}>
            {list.map((info, idx) => {
              const { input, output, time } = info;
              return (
                <TableLine
                  key={idx}
                  idx={idx}
                  type={type}
                  input={input}
                  output={output}
                  time={time}
                />
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
