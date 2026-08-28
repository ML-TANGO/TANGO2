// i18n
import { useTranslation } from 'react-i18next';

import { InputText, Radio, Textarea } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';


import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './EvalProjectFormModal.module.scss';

const cx = classNames.bind(style);

// 평가 유형 3종 — 축은 **누가 채점하나**다. 유형이 이후 실행 화면(무엇을 묻는지)과
// 유형은 점수의 척도(0~1 정답률 / 1~10 심판 점수 / 1~5 별점)를 통째로 결정하고 생성 후
// 불변이다 — 그래서 "무엇으로 채점하는지"가 읽혀야 하는데, 그 설명은 **고른 유형 하나만**
// 힌트 줄로 보여 주면 충분하다. 컨트롤은 AddModel·DockerImageFormModal 과 같은
// 디자인시스템 Radio 가로 나열이고, 수정 모드 잠금은 그쪽 선례대로 옵션별 disabled 다.
const TYPE_OPTIONS = [
  {
    value: 'reference',
    label: 'evaluation.project.type.reference',
    desc: 'evaluation.project.typeDesc.reference',
  },
  {
    value: 'judge',
    label: 'evaluation.project.type.judge',
    desc: 'evaluation.project.typeDesc.judge',
  },
  {
    value: 'expert',
    label: 'evaluation.project.type.expert',
    desc: 'evaluation.project.typeDesc.expert',
  },
];

const TYPE_VALUES = TYPE_OPTIONS.map((option) => option.value);

// 새 평가 프로젝트 생성 모달(프레젠테이셔널) — 학습/배포 모달과 동일한 프레임/필드 규격.
//   NewStyleModalFrame(664px·resize·minimize) + InputBoxWithLabel + 디자인시스템 컴포넌트.
//   필드: 이름(InputText) → 평가유형(Radio 가로 3종). **모델·데이터셋은 여기서 고르지 않는다** —
//   런을 실행하는 자리(실행 모달)에서 고른다. 한 프로젝트가 여러 모델·데이터셋의 런을
//   담을 수 있어야 비교가 성립하기 때문이다.
//   설명(선택)은 목록 카드의 본문 슬롯으로 그대로 나간다 — 모델·배포 카드가 description 을
//   본문에 싣는 것과 같은 자리다. 비워 두면 카드가 공용 플레이스홀더(no.desc)를 대신 그린다.
//   상태·검증·submit 은 컨테이너 소유(BE 계약: name/eval_type/description/workspace_id).
//   수정 모드(type==='EDIT_EVAL_PROJECT')는 하우스 관행(CREATE_/EDIT_ 가 한 모달을 공유하고
//   불변 필드를 disabled 로 잠그는 DeploymentFormModal 방식)을 그대로 따른다 — 프로젝트는
//   이름·유형이 생성 후 불변이라(유형이 점수의 척도를 통째로 결정) 설명만 열어 둔다.
function EvalProjectFormModal({
  type,
  data,
  validate,
  name,
  setName,
  evalType,
  setEvalType,
  description,
  setDescription,
  onSubmit,
}) {
  const { t } = useTranslation();
  // 수정 모드 — 컨테이너와 같은 판정(하우스의 CREATE_/EDIT_ 공유 모달 관행).
  const isEdit = type === 'EDIT_EVAL_PROJECT';

  // 고른 유형의 설명만 힌트로 세운다(전 유형 나열 X).
  const selectedTypeDesc = (() => {
    const picked = TYPE_OPTIONS.find((option) => option.value === evalType);
    return picked ? t(picked.desc) : '';
  })();
  const { submit, cancel } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => await onSubmit(),
  };

  const title = isEdit
    ? t('evaluation.project.editTitle')
    : t('evaluation.project.createTitle');

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      submitBtnTestId='create-eval-project-btn'
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        {/* ** 이름 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.name')}
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              size='medium'
              placeholder={t('evaluation.project.namePlaceholder')}
              name='name'
              value={name}
              onChange={(e) => setName(e.target.value)}
              onClear={() => setName('')}
              options={{ maxLength: 100 }}
              autoFocus={!isEdit}
              disabled={isEdit}
              disableLeftIcon
              testId='eval-project-name-input'
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>

        {/* ** 평가 유형 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.selectType')}
            labelSize='large'
            disableErrorMsg
          >
            <div className={cx('type-radio')}>
              <Radio
                name='evalType'
                selectedValue={evalType}
                options={TYPE_OPTIONS.map((option) => ({
                  label: t(option.label),
                  value: option.value,
                  labelStyle: {
                    fontSize: '14px',
                    fontFamily: 'SpoqaM',
                    textWrap: 'nowrap',
                  },
                  // 유형은 생성 후 불변 — 수정 모드에서는 전 옵션을 잠근다.
                  disabled: isEdit,
                }))}
                onChange={(e) => setEvalType(e.currentTarget.value)}
              />
            </div>
            {selectedTypeDesc && (
              <p className={cx('type-hint')}>{selectedTypeDesc}</p>
            )}
          </InputBoxWithLabel>
        </div>

        {/* ** 설명(선택) ** — 목록 카드 본문에 그대로 실린다. */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('description.label')}
            optionalText={t('optional.label')}
            labelSize='large'
            optionalSize='medium'
            disableErrorMsg
          >
            <Textarea
              size='large'
              placeholder={t('evaluation.project.descPlaceholder')}
              value={description}
              name='description'
              onChange={(e) => setDescription(e.target.value)}
              maxLength={'5000'}
              customStyle={{ fontSize: '14px' }}
              isShowMaxLength
            />
          </InputBoxWithLabel>
        </div>

        {/* 모델·데이터셋은 실행 시점 선택이라 이 폼에 없다(위 주석 참조). */}
      </div>
    </NewStyleModalFrame>
  );
}

export default EvalProjectFormModal;
