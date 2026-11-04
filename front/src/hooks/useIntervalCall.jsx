import { useEffect, useMemo } from 'react';
import { useSelector } from 'react-redux';

// Utils
import { infiniteExcute as InfiniteExcute } from '@src/utils';

/**
 * 실시간 조회를 사용하는 컴포넌트에서 사용하는 커스텀 훅
 * @param {() => Promise<boolean>} func boolean을 리턴하는 프로미스 함수
 * @param {number} delay 호출 간격
 * @param {Function} afterFirstCall 첫 호출 후 실행할 콜백 함수
 */
const useIntervalCall = (func, delay, afterFirstCall) => {
  const instance = useMemo(() => {
    return new InfiniteExcute(func);
  }, [func]);

  const { isActive } = useSelector((state) => state.tab);

  // getChartData 변경 시 infiniteExcute 객체에 새로운 함수 전달
  useEffect(() => {
    if (instance) {
      instance.setFunc(func);
    }
  }, [instance, func]);

  // 첫 진입 시 infiniteExcute 객체 생성 및 함수 설정 및 주기 호출 실행
  useEffect(() => {
    instance.start();
    return () => {
      instance.stop();
    };
  }, [instance]);

  // 현재 브라우저에서 탭을 보고 있을 때 시작 안보고 있으면 정지
  useEffect(() => {
    if (!instance) return;
    instance.setExcutionCallback((isFirst) => {
      // isFirst 첫 학습 목록 조회인지 체크하기 위한 값
      // 학습 목록 페이지로 뒤로가기를 통해 접근했을 때 이전 스크롤 위치로 이동시킴
      if (isFirst && afterFirstCall) afterFirstCall();
    });
    if (isActive) instance.start();
    else instance.stop();
  }, [instance, isActive, afterFirstCall]);

  // 딜레이 설정
  useEffect(() => {
    if (instance && delay) instance.setDelay(delay);
  }, [instance, delay]);
};

export default useIntervalCall;
