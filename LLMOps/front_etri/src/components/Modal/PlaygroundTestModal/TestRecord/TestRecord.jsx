import { Textarea } from '@tango/ui-react';

import { getPlaygroundTestLog } from '@src/apis/llm/playground';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-toastify';

import Dropdown from '@src/components/atoms/Dropdown';
import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import TooltipPortal from '@src/hooks/TooltipPortal';

import { STATUS_SUCCESS } from '@src/network';

// CSS module
import classNames from 'classnames/bind';
import style from './TestRecord.module.scss';

const cx = classNames.bind(style);

const dataTypeObj = {
  question: '질문 입력',
  dataset: '데이터셋',
};

const TableLine = ({ idx, type, input, output, time }) => {
  const inputContent = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  return (
    <>
      <div
        ref={inputContent}
        className={cx('tr', idx % 2 === 1 && 'purple')}
        key={idx}
        onMouseEnter={() => setIsShowTooltip(true)}
        onMouseLeave={() => setIsShowTooltip(false)}
      >
        <div className={cx('td')}>{type}</div>
        <div className={cx('td')}>{input}</div>
        <div className={cx('td')}>{output}</div>
        <div className={cx('td')}>{time}초</div>
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
                유형: {type}
              </p>
              <p
                style={{
                  wordBreak: 'break-word',
                  overflowWrap: 'break-word',
                  whiteSpace: 'normal',
                }}
              >
                입력 내용: {input}
              </p>
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
            </div>
          }
        />
      </TooltipPortal>
    </>
  );
};

const getPlaygroundLogData = async (playgroundId, setLogData) => {
  const { status, result, message } = await getPlaygroundTestLog(playgroundId);
  if (status === STATUS_SUCCESS) {
    setLogData(result);
  } else {
    toast.error(message);
  }
};

export default function TestRecord({ playgroundId }) {
  const { t } = useTranslation();

  const [logData, setLogData] = useState([]);

  useEffect(() => {
    getPlaygroundLogData(playgroundId, setLogData);
  }, [playgroundId]);

  return (
    <div className={cx('table')}>
      <div className={cx('thead')}>
        <div className={cx('tr')}>
          <div className={cx('th')}>유형</div>
          <div className={cx('th')}>입력 내용</div>
          <div className={cx('th')}>출력 내용</div>
          <div className={cx('th')}>응답 시간</div>
        </div>
      </div>
      <div className={cx('tbody')}>
        {logData.length === 0 && (
          <p className={cx('nodata')}>데이터가 존재하지 않습니다.</p>
        )}
        {logData.map((el, idx) => {
          return (
            <TableLine
              key={idx}
              idx={idx}
              type={dataTypeObj[el.type]}
              input={el.input}
              output={el.output}
              time={el.response_time}
            />
          );
        })}
      </div>
    </div>
  );
}
