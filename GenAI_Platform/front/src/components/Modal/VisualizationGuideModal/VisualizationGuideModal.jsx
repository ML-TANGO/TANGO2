import React, { useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import ModalFrame from '../ModalFrame';

import classNames from 'classnames/bind';
import style from './VisualizationGuideModal.module.scss';

const cx = classNames.bind(style);

const VisualizationGuideModal = ({ type, data }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [guideLog, setGuideLog] = useState('');

  const { submit } = data;

  const newSubmit = {
    text: submit.text,
    func: () => {
      dispatch(closeModal('VISUALIZATION_GUIDE'));
    },
  };

  const fetchGuideLog = async () => {
    const logResponse = await callApi({
      url: `projects/training-log-guide?training_type=training`,
      method: 'get',
    });

    const { result, status } = logResponse;

    if (status === STATUS_SUCCESS) {
      setGuideLog(result);
    }
  };

  return (
    <ModalFrame
      submit={newSubmit}
      type={type}
      validate={true}
      title={t('visualizationGuide.header')}
      customStyle={{
        width: '684px',
      }}
      isResize={true}
      isMinimize={true}
    >
      <h2 className={cx('title')}>{t('visualizationGuide.header')}</h2>
      <div className={cx('form')}>
        <div className={cx('desc-template')}>
          <div className={cx('first')}>
            <div className={cx('number')}>1</div>
            <span className={cx('text')}>반복문 설정</span>
          </div>
          <div className={cx('second')}>
            <div className={cx('left-bar')}></div>
            <div className={cx('desc')}>
              <span className={cx('first-text')}>
                먼저, 학습을 반복하는 기본 구조를 설정합니다. 여기서는 Epoch을
                기준으로 반복문을 구성
                <br />
                합니다.
              </span>
              <span className={cx('second-text')}>
                for epoch in range(EPOCHS): EPOCHS는 모델이 학습할 총 Epoch
                횟수를 의미합니다.
                <br />각 Epoch마다 모델의 학습이 진행되고, 반복문 내에서 학습
                결과가 기록됩니다
              </span>
              <div className={cx('command')}>
                <span>for epoch in range(EPOCHS):</span>
                <span className={cx('left-indent')}>
                  # EPOCHS는 총 학습할 epoch의 수입니다.
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className={cx('desc-template')}>
          <div className={cx('first')}>
            <div className={cx('number')}>2</div>
            <span className={cx('text')}>필수 값: iteration_key</span>
          </div>
          <div className={cx('second')}>
            <div className={cx('left-bar')}></div>
            <div className={cx('desc')}>
              <span className={cx('first-text')}>
                학습 과정에서 반복 요소를 기록합니다. 이 경우 epoch을 기준으로
                학습이 진행되고 있으므
                <br />
                로, 필수 값인 iteration_key를 epoch으로 설정하여 JSON 포맷에
                포함합니다.
              </span>
              <span className={cx('second-text')}>
                iteration_key는 그래프의 x축에 해당하는 반복 요소를 정의하는
                필드입니다.
                <br />이 가이드에서는 epoch이 반복 요소로 설정되었습니다.
              </span>
              <div className={cx('command')}>
                <span># 필수 값: iteration (그래프의 x 축 설정 값)</span>
                <span className={cx('left-indent')}>
                  {` print(f'[FLIGHTBASE] {{ "iteration_key" : "epoch", "epoch" : {epoch}')`}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className={cx('desc-template')}>
          <div className={cx('first')}>
            <div className={cx('number')}>3</div>
            <span className={cx('text')}>추가 파라미터들 설정</span>
          </div>
          <div className={cx('second')}>
            <div style={{ height: '174px' }} className={cx('left-bar')}></div>
            <div className={cx('desc')}>
              <span className={cx('first-text')}>
                각 반복(epoch)에서 모델 학습의 추가 파라미터(parameter1,
                parameter2)를 출력합니
                <br />
                다.
              </span>
              <div style={{ height: '106px' }} className={cx('command')}>
                <span># 손실 값과 파라미터는 각 epoch마다 업데이트됩니다.</span>
                <span className={cx('left-indent')}>
                  loss = 0.021 * epoch # 예시 손실 값
                </span>
                <span className={cx('left-indent')}>
                  value1 = 0.5 * epoch # 예시 파라미터1 값
                </span>
                <span className={cx('left-indent')}>
                  value2 = 0.3 * epoch # 예시 파라미터2 값
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className={cx('desc-template')}>
          <div className={cx('first')}>
            <div className={cx('number')}>4</div>
            <span className={cx('text')}>사라지는 필드 값</span>
          </div>
          <div className={cx('second')}>
            <div style={{ height: '56px' }} className={cx('left-bar')}></div>
            <div className={cx('desc')}>
              <span className={cx('first-text')}>
                log나 timestamp와 같은 필드는 학습 결과에서 제외해야 합니다. 이
                부분은 명시적으로 코
                <br />
                딩할 필요는 없지만, 가이드에서는 해당 필드를 출력하지 않도록
                합니다.
              </span>
            </div>
          </div>
        </div>

        <div className={cx('desc-template')}>
          <div className={cx('first')}>
            <div className={cx('number')}>5</div>
            <span className={cx('text')}>JSON 포맷으로 결과 출력</span>
          </div>
          <div className={cx('second')}>
            <div className={cx('left-bar', 'white')}></div>
            <div className={cx('desc')}>
              <span className={cx('first-text')}>
                모든 정보를 JSON 포맷으로 출력합니다. 이를 위해 epoch, loss,
                parameter1,
                <br />
                parameter2를 포함한 포맷을 구성합니다.
              </span>
              <div style={{ height: '100px' }} className={cx('command')}>
                <span># 반드시 JSON 포맷으로 출력</span>
                <span className={cx('left-indent')}>
                  {`print(f'[FLIGHTBASE] {{ "iteration_key" : "epoch", "epoch" :`}
                  <br />
                  {`{epoch}, "loss": {loss}, "parameter1": {value1}, "parameter2": `}
                  <br />
                  {`{value2} }}')`}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className={cx('middle-divider')}></div>

        <div className={cx('code-container')}>
          <div className={cx('box')}>
            <span className={cx('text')}>전체코드</span>
            <div className={cx('command')}>
              <span>for epoch in range(EPOCHS):</span>
              <div className={cx('sub')}>
                <span># 손실 값과 파라미터는 각 epoch마다 업데이트됩니다.</span>
                <span>loss = 0.021 * epoch # 예시로 가정한 손실 값</span>
                <span>value1 = 0.5 * epoch # 예시 파라미터1 값</span>
                <span>value2 = 0.3 * epoch # 예시 파라미터2 값</span>
                <div className={cx('empty-div')}></div>
                <span># 필수 값: iteration (그래프의 x 축 설정 값)</span>
                <span># 사라지는 필드: log, timestamp</span>
                <span># 반드시 JSON 포맷으로 출력</span>
                <span>
                  {`print(f'[FLIGHTBASE] {{ "iteration_key" : "epoch", "epoch" : {epoch},`}
                  <br />
                  {`"loss": {loss}, "parameter1": {value1}, "parameter2": {value2} }}')`}
                </span>
              </div>
            </div>
          </div>

          <div className={cx('box')}>
            <span className={cx('text')}>출력 예시</span>
            <div className={cx('command')}>
              <span>
                {`[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 1 , "loss": `}
                <br />
                {`0.021136578172445297, "parameter1": 0.5, "parameter2": 0.3 }`}
              </span>
              <span>
                {`[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 2 , "loss": `}
                <br />
                {`0.04227315634489059, "parameter1": 1.0, "parameter2": 0.6 }`}
              </span>
              <span>
                {`[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 3 , "loss": `}
                <br />
                {`0.06340973451733588, "parameter1": 1.5, "parameter2": 0.9 }`}
              </span>
            </div>
          </div>

          <div className={cx('box')}>
            <span className={cx('text')}>그래프 예시</span>
            <img
              className={cx('graph')}
              src='/images/custom/sample-graph.png'
              alt='graph'
            />
          </div>
        </div>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(VisualizationGuideModal);
