// Components
import GPUAllocationStatus from './GPUAllocationStatus';

import classNames from 'classnames/bind';
import style from './GPUServerTab.module.scss';

const cx = classNames.bind(style);

/**
 * GPU 서버 탭 컴포넌트
 *
 * 위치: 어드민 로그인 - 노드 관리 페이지 - GPU 서버 탭
 *
 * @component
 * @example
 *
 * return (
 *  <GPUServerTab />
 * );
 */
function GPUServerTab() {
  return (
    <div className={cx('gpu-server-tab')}>
      <div className={cx('dashboard', 'margin-item')}>
        {/*
          전체 GPU 할당 상태 파이 그래프,
          GPU MIG 할당 상태 스택바 그래프,
          GPU별 노드별 할당률 테이블 컴포넌트
        */}
        <GPUAllocationStatus />
        {/* 실시간 GPU 할당, MIG 할당 그래프 컴포넌트 */}
        {/* <GPUUsageRealTimeChart /> */}
      </div>
      {/* GPU 노드 목록 테이블 */}
      {/* <NodeTable serverType='gpu' /> */}
    </div>
  );
}

export default GPUServerTab;
