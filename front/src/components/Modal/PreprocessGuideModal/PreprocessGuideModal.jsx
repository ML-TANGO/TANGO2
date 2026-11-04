import React from 'react';
import { useDispatch } from 'react-redux';

import { closeModal } from '@src/store/modules/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './PreprocessGuideModal.module.scss';

const cx = classNames.bind(style);

const PreprocessGuideModal = ({ data, type }) => {
  const dispatch = useDispatch();
  const { submit, builtInDataType } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      dispatch(closeModal(type));
    },
  };

  const dataTypes = [
    {
      type: 'Text',
      work: [
        '토큰화, 불용어 제거, 정규화, 문장 분할',
        '특수 문자 제거 및 소문자 변환',
      ],
      format: '.txt, .csv, JSON(텍스트 데이터 포함)',
    },
    {
      type: 'Image',
      work: [
        '크기 조정, 채널 변환(RGB/Grayscale), 정규화',
        '데이터 증강(회전, 뒤집기, 자르기 등)',
      ],
      format: '.jpg, .png, .bmp',
    },
    {
      type: 'Tabular',
      work: [
        '누락 데이터 처리, 스케일링, 범주형 데이터 인코딩',
        '상관관계 분석 및 데이터 선택',
      ],
      format: '.csv, .xlsx',
    },
    {
      type: 'Audio',
      work: ['샘플링 레이트 변환, 노이즈 제거, 스펙트로그램 생성'],
      format: '.wav, .mp3',
    },
    {
      type: 'Video',
      work: ['프레임 추출, 해상도 변환, 데이터 증강'],
      format: '.mp4, .avi',
    },
  ];

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      isResize={true}
      isMinimize={true}
      type={type}
      customStyle={{ maxHeight: '750px' }}
      validate={true}
      title={'전처리기 사용 가이드'}
    >
      <div className={cx('row')}>
        <div className={cx('text-header')}>
          <div className={cx('number')}>1</div>
          <span>데이터 유형별 안내</span>
        </div>
        {dataTypes.map(({ type, work, format }) => (
          <div className={cx('type-box')} key={type}>
            <span className={cx('type')}>{type}</span>
            <div className={cx('work-list')}>
              <span>주요 전처리 작업</span>
              {work.map((value, index) => (
                <span key={index} className={cx('work-info')}>
                  {value}
                </span>
              ))}
            </div>
            <div className={cx('format-list')}>
              <span>지원 형식</span>
              <span className={cx('format-info')}>{format}</span>
            </div>
          </div>
        ))}
        <div className={cx('middle-line')}></div>
        <div className={cx('text-header')}>
          <div className={cx('number')}>2</div>
          <span>선택한 데이터 유형에 따른 데이터셋 및 데이터 형식 안내</span>
        </div>
        <div className={cx('type-box')}>
          <span className={cx('type')}>데이터셋 안내</span>
          <div className={cx('work-list')}>
            <span className={cx('')}>권장 데이터 크기</span>
            <span className={cx('work-info')}>최소 10,000개의 샘플</span>
            <span className={cx('work-info')}>
              각 샘플의 텍스트 길이: 평균 50 ~ 200자
            </span>
          </div>
          <div className={cx('format-list')}>
            <span>지원 형식</span>
            <span className={cx('format-info')}>.txt, .csv, .json</span>
          </div>
        </div>
        <div className={cx('type-box')}>
          <span className={cx('type')}>데이터셋 형식 안내</span>
          <div className={cx('work-list')}>
            <span className={cx('')}>필수 필드</span>
            <span className={cx('work-info')}>
              문장: 텍스트 데이터가 들어가는 필드
            </span>
            <span className={cx('work-info')}>
              레이블(선택): 데이터에 대한 분류 또는 태그(감성, 카테고리 등)
            </span>
          </div>
          <div className={cx('data-format-list')}>
            <span className={cx('title')}>지원되는 데이터 형식</span>
            <div className={cx('detail-box')}>
              <span className={cx('format-type')}>CSV 형식</span>
              <div className={cx('gray-box')}>
                문장,레이블
                <br />
                오늘 날씨가 정말 좋다,긍정
                <br />이 영화는 매우 지루했다,부정
                <br />이 제품은 최고야! 다시 사고 싶다,긍정
              </div>
            </div>
            <div className={cx('detail-box')}>
              <span className={cx('format-type')}>JSON 형식</span>
              <div className={cx('gray-box')}>
                &#91;
                <br />
                &nbsp; &nbsp; &#123; &#34;문장&#34;: &#34;오늘 날씨가 정말
                좋다&#34;, &#34;레이블&#34;: &#34;긍정&#34;&#125;
                <br />
                &nbsp; &nbsp; &#123; &#34;문장&#34;: &#34;이 영화는 매우
                지루했다&#34;, &#34;레이블&#34;: &#34;부정&#34;&#125;
                <br />
                &nbsp; &nbsp; &#123; &#34;문장&#34;: &#34;이 제품은 최고야! 다시
                사고 싶다&#34;, &#34;레이블&#34;: &#34;긍정&#34;&#125;
                <br />
                &#93;
              </div>
            </div>
            <div className={cx('detail-box')}>
              <span className={cx('format-type')}>TEXT 형식</span>
              <div className={cx('gray-box')}>
                오늘 날씨가 정말 좋다
                <br />이 영화는 매우 지루했다
                <br />이 제품은 최고야! 다시 사고 싶다
              </div>
            </div>
          </div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default PreprocessGuideModal;
