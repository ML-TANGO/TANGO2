import React from 'react';

// CSS Module
import classNames from 'classnames/bind';
import style from './TooltipContent.module.scss';

const cx = classNames.bind(style);

export default function TooltipContent() {
  return (
    <div className={cx('tooltip')}>
      <p className={cx('title')}>데이터 수집 접근 권한</p>
      <div className={cx('contents')}>
        <p>
          Private으로 설정한 경우 사용자를 선택하여 특정 사용자에게만 사용
          권한을 부여할 수 있습니다.
        </p>
        <p>
          선택된 사용자는 수집 실행만 가능하며 데이터 수집을 수정하거나 삭제할
          수 없습니다.
        </p>
        <p>단, 워크스페이스 매니저는 소유자와 동일하게 모든 권한을 가집니다.</p>
      </div>
    </div>
  );
}
