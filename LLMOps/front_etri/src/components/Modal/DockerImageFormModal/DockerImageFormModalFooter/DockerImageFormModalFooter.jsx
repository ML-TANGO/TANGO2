import { useState } from 'react';
import { connect } from 'react-redux';

// i18n
import { withTranslation } from 'react-i18next';

// storybook
import { Button } from '@tango/ui-react';

// HOC
import EnterSubmitHOC from '@src/hoc/EnterSubmitHOC';

// module
import { closeModal } from '@src/store/modules/modal';

// CSS module
import classNames from 'classnames/bind';
import style from './DockerImageFormModalFooter.module.scss';
const cx = classNames.bind(style);

const hocParam = {};

function DockerImageFormModalFooter({
  submit,
  submitBtnTestId,
  cancel,
  closeModal: close, //* type을 close에 넘기고 있다
  type,
  validate,
  prev,
  next,
  nextValidate,
  totalStep,
  currentStep,
  t,
  footerMessage,
}) {
  const [loading, setLoading] = useState(false);

  hocParam.onSubmitEvent = (e) => {
    if (e === undefined) {
      return null;
    }
    if (submit.func && !loading && validate) {
      setLoading(true);
      const response = submit.func();
      if (response) {
        response.then((result) => {
          if (result) {
            close(type);
          } else {
            setLoading(false);
          }
        });
      } else {
        setLoading(false);
      }
    }
  };

  hocParam.onPrevStep = () => {
    if (prev.func && !loading) {
      setLoading(true);
      prev.func();
      const response = prev.func();
      if (response) {
        response.then(() => {
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    }
  };

  hocParam.onNextStep = () => {
    if (next.func && !loading) {
      setLoading(true);
      next.func();
      const response = next.func();
      if (response) {
        response.then(() => {
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    }
  };

  return (
    <div className={cx('modal-footer')}>
      <div className={cx('error-message')}>{footerMessage}</div>
      <div className={cx('left')}>
        {prev && (
          <Button
            disabled={Number(currentStep) === 1}
            onClick={hocParam.onPrevStep}
          >
            {t(prev.text)}
          </Button>
        )}
        {next && (
          <Button
            disabled={totalStep === currentStep || !nextValidate}
            onClick={hocParam.onNextStep}
          >
            {t(next.text)}
          </Button>
        )}
      </div>
      <div className={cx('right')}>
        {cancel && (
          <Button
            onClick={() => {
              close(type);
              if (cancel.func) {
                cancel.func();
              }
            }}
            type={'none-border'}
          >
            {t(cancel.text)}
          </Button>
        )}
        {submit && (
          <Button
            onClick={(e) => hocParam.onSubmitEvent(e)}
            disabled={!validate}
            loading={loading ? true : false}
            testId={submitBtnTestId}
          >
            {t(submit.text)}
          </Button>
        )}
      </div>
    </div>
  );
}

export default withTranslation()(
  connect(null, { closeModal })(
    EnterSubmitHOC(hocParam)(DockerImageFormModalFooter),
  ),
);
