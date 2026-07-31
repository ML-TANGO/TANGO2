// Components
import NodeTable from '../NodeTable';
import CPUAllocationStatus from './CPUAllocationStatus';
import CPUUsageRealTimeChart from './CPUUsageRealTimeChart';
import RamUsageRealTimeChart from './RamUsageRealTimeChart';
import RamUsageStatus from './RamUsageStatus';

// CSS module
import style from './CPUServerTab.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

/**
 * CPU 서버 탭 컴포넌트
 *
 * 위치: 어드민 로그인 - 노드 관리 페이지 - CPU 서버 탭
 *
 * @component
 * @example
 *
 * return (
 *  <CPUServerTab />
 * );
 */
function CPUServerTab() {
  return (
    <div className={cx('cpu-server-tab')}>
      <div className={cx('dashboard')}>
        {/* 
          CPU 코어 할당 상태 파이 그래프,
          CPU 모델별 코어 할당률 테이블 컴포넌트
        */}
        <CPUAllocationStatus />
        {/* 실시간 CPU 이용률, 할당 그래프 */}
        {/* <CPUUsageRealTimeChart /> */}
      </div>
      <div className={cx('dashboard', 'margin-item')}>
        {/*
          RAM을 사용 중인 노드 파이 그래프,
          노드별 RAM 사용률 테이블 컴포넌트
        */}
        <RamUsageStatus />
        {/* 실시간 RAM 사용률, 할당 그래프 */}
        {/* <RamUsageRealTimeChart /> */}
      </div>
      {/* CPU 노드 목록 테이블 */}
      {/* <NodeTable serverType='cpu' /> */}
    </div>
  );
}

export default CPUServerTab;
