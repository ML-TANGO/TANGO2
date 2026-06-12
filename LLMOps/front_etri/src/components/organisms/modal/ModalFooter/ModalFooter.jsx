import { useCallback, useEffect } from 'react';
import { useDispatch } from 'react-redux';

// Actions
import { closeModal } from '@src/store/modules/modal';

// Atoms
import { Button } from '@tango/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './ModalFooter.module.scss';
const cx = classNames.bind(style);

/**
 * 모달 Footer 컴포넌트 (organisms)
 * @param {{
 *  submit: { text: string, func: Function},
 *  cancel: { text: string, func: Function},
 *  type: string,
 *  isValidate: boolean,
 * }} param
 *
 * @component
 * @example
 *
 *
 * const submit = {
 *  text: 'Submit',
 *  func: () => {
 *    // 버튼 클릭 시 실행 함수
 *  },
 * };
 *
 * const cancel = {
 *  text: 'Cancel',
 *  func: () => {
 *    // 버튼 클릭 시 실행 함수
 *  },
 * };
 *
 * return (
 *  <ModalFooter submit={submit} cancel={cancel} type='CREATE_TRAINING' isValidate={true} />
 * );
 *
 */
function ModalFooter({
  submit,
  cancel,
  type,
  isValidate,
  loading,
  leftButtonType,
  deployFooterMessage,
}) {
  // Redux Hooks
  const dispatch = useDispatch();

  // Cancel Function
  const cancelFunc = useCallback(() => {
    if (cancel.func) cancel.func();
    dispatch(closeModal(type));
  }, [cancel, dispatch, type]);

  // Submit Function
  const submitFunc = async () => {
    if (submit.func) {
      const res = await submit.func();
      if (res) dispatch(closeModal(type));
    }
  };

  const keyboardEvent = useCallback(
    (event) => {
      if (event?.keyCode === 27) {
        dispatch(closeModal(type));
      }
    },
    [dispatch, type],
  );

  useEffect(() => {
    document.addEventListener('keydown', keyboardEvent);
  }, [keyboardEvent]);

  return (
    <div className={cx('footer')}>
      <div className={cx('error-message')}>{deployFooterMessage}</div>
      <div className={cx('button')}>
        <Button type='none-border' onClick={cancelFunc}>
          {cancel.text}
        </Button>
        <Button
          type={leftButtonType || 'primary'}
          onClick={submitFunc}
          disabled={!isValidate}
          loading={loading}
        >
          {submit.text}
        </Button>
      </div>
    </div>
  );
}

export default ModalFooter;
