import { useState, Fragment } from 'react';

// Atoms
import Button from '@src/components/atoms/button/Button';
import { Checkbox } from '@jonathan/ui-react';

// Molecules
import GuideBox from '@src/components/molecules/GuideBox/GuideBox';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// CSS Module
import classNames from 'classnames/bind';
import style from './DroneChallengeModalContent.module.scss';
const cx = classNames.bind(style);

// 리더보드 URL
const LEADERBOARD_URL = import.meta.env
  .VITE_REACT_APP_CHALLENGE_LEADERBOARD_URL;

/**
 * DNA+DRONE CHALLENGE 답안지 제출 모달
 * @param {Object} props - 노드 모달 폼 데이터
 * @param {'DRONE_CHALLENGE'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => {} | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => {} | undefined,
 *      text: string | undefined,
 *    },
 *    trainingId: number | undefined,
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트) 및 trainingId 값
 * @param {() => JSX.Element | undefined} props.renderTestInputForm - 답안지 테스트 렌더 함수
 * @param {() => JSX.Element | undefined} props.renderSubmitInputForm - 답안지 제출 인풋 컴포넌트 렌더 함수
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true 하나라도 유효하지 않으면 false
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @component
 * @returns {JSX.Element}
 */
function DroneChallengeModalContent({
  type,
  modalData,
  renderTestInputForm,
  renderSubmitInputForm,
  isValidate,
  onSubmit,
  loading,
}) {
  const [currentStep, setCurrentStep] = useState(1);
  const [guideCheck, setGuideCheck] = useState(false);

  const { submit, cancel } = modalData;
  const newSubmit = {
    text: currentStep === 1 ? '제출 바로가기' : '제출하기',
    func: async () => {
      if (currentStep === 1) {
        setCurrentStep(2);
      } else if (currentStep === 2) {
        const res = await onSubmit(submit.func);
        return res;
      }
      return false;
    },
  };
  return (
    <ModalTemplate
      headerRender={<ModalHeader title='답안지 테스트 &amp; 제출' />}
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          type={type}
          isValidate={
            currentStep === 1 ? true : isValidate && guideCheck && !loading
          }
        />
      }
      loading={loading}
    >
      <div className={cx('modal-content')}>
        <div className={cx('tab-box')}>
          <p
            className={cx(
              'input-group-title',
              'test',
              currentStep === 1 && 'active',
            )}
            onClick={() => setCurrentStep(1)}
          >
            답안지 테스트
          </p>
          <p
            className={cx(
              'input-group-title',
              'submit',
              currentStep === 2 && 'active',
            )}
            onClick={() => {
              setCurrentStep(2);
            }}
          >
            제출
          </p>
        </div>
        {currentStep === 1 && (
          <Fragment>
            <div className={cx('info-box')}>
              <GuideBox
                title='답안지 테스트 안내'
                isTitleIcon
                textList={[
                  '테스트할 모델의 정답지를 csv 형식으로 생성합니다.',
                  '테스트할 답안지를 아래에서 선택합니다.',
                  '테스트 실행 버튼을 클릭하여 답안지의 AP를 확인합니다.',
                ]}
                noticeList={[
                  '*테스트를 통해 산출된 AP는 최종 평가 점수가 아닙니다.',
                ]}
              />
            </div>
            {renderTestInputForm()}
          </Fragment>
        )}
        {currentStep === 2 && (
          <Fragment>
            <div className={cx('info-box')}>
              <GuideBox
                title='제출 안내'
                isTitleIcon
                textList={[
                  '리더보드에 제출할 답안지와 답안지 생성을 위한 내용을 제출합니다.',
                  `<b>답안지 제출은 하루 3회로 제한</b>되오니 주의해주시기 바랍니다.`,
                  '새로 제출된 내용은 이전에 제출된 내용을 대체하며, 이전에 제출된 내용은 저장되지 않습니다.',
                  `챌린지 종료 전 가장 <b>마지막에 제출된 내용이 최종 제출물</b>로 선정됩니다.`,
                ]}
              />
              <GuideBox
                title='입력내용 안내'
                isTitleIcon={false}
                textList={[
                  `학습 코드 관련<br/>
                  - 학습코드를 선택하고, 필요시 학습 실행을 위한 command(parser only)를 입력합니다.`,
                  `답안지 관련<br/>
                  - 답안지 : 2번의 답안지 생성 코드로 생성된 답안지를 선택합니다.<br/>
                  - 답안지 생성 코드 : 코드에는 dataset path parameter가 필수적으로 포함되어 있어야 합니다.<br/>
                  - 답안지 생성 commnad : 답안지 생성 코드 실행시 필요한 parameter와 답안지 생성 command(parser only)가 입력되어야 합니다.<br/>
                    예시)  --weights runs/train/exp/weights/best.pt <br/>--domain /home/dnadrone/datasets_rw/dna-challenge/validation/images/`,
                  `추론 시간 관련<br/>
                  - 추론 시간 : 이미지 한 장을 추론하는데 걸리는 시간을 ms 단위로 입력합니다.`,
                  `도커 이미지 관련<br/>
                  - 패키지 설치 스크립트 파일 : 패키지가 설치된 도커 사용시, 패키지 설치를 위한 스크립트 파일을 제출해야 합니다.`,
                ]}
              />
              <GuideBox
                title='최종채점 진행방식 안내'
                isTitleIcon={false}
                subtitle='제출된 내용은 아래 예시에 안내된 최종채점 진행방식으로 이상없이 작동할 수 있어야 합니다.'
                textList={[
                  `<strong>제출내용 예시</strong><br/>
                  <img src='/images/custom/DNA+DRONE_challenge_guide.png' alt='example' width='560px' style='margin:8px 0 12px' />`,
                  `<strong>최종채점 진행방식</strong><br/>
                  1) 패키지 설치<br/>
                  &nbsp;&nbsp;&nbsp;&nbsp;./installer-package.sh<br/>
                  2) Private 데이터셋 기반 답안지 생성<br/>
                  &nbsp;&nbsp;&nbsp;&nbsp;python answer_sheet_creator.py --datapath /PRIVATE_DATASET`,
                ]}
                noticeList={[
                  '*선택한 파일을 업로드 하는 것은 아닙니다. 따라서 선택한 파일이 반드시 작업 환경에서 동일한 위치에 존재하도록 유지해야 합니다.',
                  '*최종 제출 후 파일이 업데이트 되었을 경우 발생하는 불이익은 사용자에게 책임이 있습니다.',
                  '*챌린지 종료 전 제출 요청이 급증할 경우 제출이 원활하지 않을 수 있습니다.',
                  '*기타 자세한 사항은 챌린지 안내 문서를 참고하시기 바랍니다.',
                ]}
              />
              <div className={cx('action-box')}>
                <Checkbox
                  label='제출 전 위 안내 내용을 확인했습니다.'
                  name='guideCheck'
                  customLabelStyle={{ paddingBottom: '3px' }}
                  checked={guideCheck}
                  onChange={() => {
                    setGuideCheck(!guideCheck);
                  }}
                />
                <Button
                  size='medium'
                  type='transparent'
                  rightIcon='/images/icon/00-ic-basic-external-link-blue.svg'
                  onClick={() => window.open(LEADERBOARD_URL, '_blank')}
                >
                  리더보드 바로가기
                </Button>
              </div>
            </div>
            {renderSubmitInputForm()}
          </Fragment>
        )}
      </div>
    </ModalTemplate>
  );
}

export default DroneChallengeModalContent;
