import { useCallback, useState, useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import ProgressStatusItem from './ProgressStatusItem';
import { Button } from '@jonathan/ui-react';

// Actions
import { closeProgressList } from '@src/store/modules/progressList';

// CSS Module
import classNames from 'classnames/bind';
import style from './ProgressStatusList.module.scss';
const cx = classNames.bind(style);

ProgressStatusList.defaultProps = {
  progressList: [],
};

function ProgressStatusList({ progressList }) {
  const { t } = useTranslation();
  const [doneCount, setDoneCount] = useState(0);
  const popupRef = useRef(null);
  const dispatch = useDispatch();

  const countHandler = useCallback(() => {
    setDoneCount((prevCount) => prevCount + 1);
  }, []);

  // LifeCycle
  useEffect(() => {
    window.onbeforeunload = function (e) {
      var dialogText = 'Dialog text here';
      e.returnValue = dialogText;
      return dialogText;
    };

    const { current: popupEle } = popupRef;
    // 애니메이션
    setTimeout(() => {
      if (popupEle) {
        popupEle.style.bottom = '0px';
        popupEle.style.opacity = '1';
      }
    }, 1);
    return () => {
      window.onbeforeunload = null;
      if (popupEle) {
        popupEle.style.top = '0';
        popupEle.style.opacity = '0';
      }
    };
  }, []);

  return (
    <div className={cx('progress-status-box')} ref={popupRef}>
      <div className={cx('top')}>
        <Button
          type='secondary'
          size='x-small'
          disabled={doneCount !== progressList.length}
          onClick={() => {
            dispatch(closeProgressList());
          }}
        >
          {t('close.label')}
        </Button>
      </div>

      <ul className={cx('progress-list')}>
        {progressList.map((data, key) => (
          <ProgressStatusItem
            key={key}
            data={data}
            title={data.title}
            rate={data.rate}
            countHandler={countHandler}
          />
        ))}
      </ul>
    </div>
  );
}

export default ProgressStatusList;
