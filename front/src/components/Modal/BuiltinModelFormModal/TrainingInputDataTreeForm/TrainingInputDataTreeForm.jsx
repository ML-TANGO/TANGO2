import { useState, useEffect } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';
import InputDataForm from './InputDataForm';

// CSS module
import classNames from 'classnames/bind';
import style from './TrainingInputDataTreeForm.module.scss';
const cx = classNames.bind(style);

const TrainingInputDataTreeForm = ({
  trainingInputDataForm,
  addInputForm,
  removeInputForm,
  inputHandler, // 입력 이벤트 핸들러
}) => {
  const { t } = useTranslation();
  /**
   * 모두 펼치기, 모두 접기 상태 클릭시 토글
   * true/false 값 상관없이
   * InputDataForm에서 상태 변화 감지시 해당 이벤트 실행
   */
  const [allOpen, setAllOpen] = useState(false);
  const [allClose, setAllClose] = useState(false);
  const [list, setList] = useState(trainingInputDataForm);

  useEffect(() => {
    if (list !== trainingInputDataForm) {
      setList([...trainingInputDataForm]);
    }
    if (list.length === 1) {
      // 루트 폴더만 있을 경우 입력 창을 오픈
      setAllOpen(!allOpen);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trainingInputDataForm]);

  return (
    <div className={cx('training-input-data-form')}>
      <div className={cx('input-data-list')}>
        {list.map((data, idx) => {
          return (
            <InputDataForm
              key={idx}
              idx={idx}
              data={data}
              addInputForm={addInputForm}
              removeInputForm={removeInputForm}
              inputHandler={inputHandler}
              allOpen={allOpen}
              allClose={allClose}
            />
          );
        })}
      </div>
      <div className={cx('btn-wrap')}>
        <div className={cx('fold-btn-box')}>
          <Button
            type='secondary'
            icon='/images/icon/ic-arrow-up-white.svg'
            iconStyle={{
              width: '24px',
              height: '24px',
            }}
            onClick={() => setAllOpen(!allOpen)}
            disabled={list.length === 0}
          >
            {t('allExpand.label')}
          </Button>
          <Button
            type='secondary'
            icon='/images/icon/ic-arrow-up-white.svg'
            iconStyle={{
              width: '24px',
              height: '24px',
              transform: 'rotate(180deg)',
            }}
            onClick={() => {
              setAllClose(!allClose);
            }}
            disabled={list.length === 0}
          >
            {t('allCollapse.label')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default TrainingInputDataTreeForm;
