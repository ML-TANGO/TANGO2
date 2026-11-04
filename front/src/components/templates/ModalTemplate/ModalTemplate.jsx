import { useEffect, useRef } from 'react';

// Components
import Loading from '@src/components/atoms/loading/Loading';

// CSS Module
import classNames from 'classnames/bind';
import style from './ModalTemplate.module.scss';

const cx = classNames.bind(style);

/**
 * 모달 템플릿 컴포넌트
 * 헤더, 컨텐트, 푸터 컴포넌트를 인자로 모달 형태로 합쳐주는 템플릿 컴포넌트
 * @param {Object} props 헤더, 컨텐트, 푸터 컴포넌트 파라미터
 * @param {JSX.Element | undefined} props.headerRender 헤더 컴포넌트 렌더
 * @param {JSX.Element | undefined} props.children 컨텐트 컴포넌트 렌더
 * @param {JSX.Element | undefined} props.footerRender 푸터 컴포넌트 렌더
 * @returns {JSX.Element} 모달 컴포넌트
 */
function ModalTemplate({
  children,
  headerRender,
  footerRender,
  loading,
  customStyle,
}) {
  const modalRef = useRef();
  const boxShadowRef = useRef();

  // LifeCycle
  useEffect(() => {
    // 애니메이션
    const modal = modalRef.current;

    setTimeout(() => {
      if (modal) {
        modal.style.opacity = 1;
      }
    }, 1);
    return () => {
      if (modal) {
        modal.style.opacity = 0;
      }
    };
  }, [modalRef]);

  return (
    <div className={cx('shadow')} ref={boxShadowRef}>
      <div
        style={customStyle?.component}
        className={cx('modal')}
        ref={modalRef}
      >
        {loading && (
          <div className={cx('dim')}>
            <Loading
              customStyle={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
              }}
            />
          </div>
        )}
        {headerRender}
        <div className={cx('modal-content-wrap')}>{children}</div>
        {footerRender}
      </div>
    </div>
  );
}

export default ModalTemplate;
