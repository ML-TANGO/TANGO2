import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText, Textarea } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { createDataset } from '@src/apis/llm/dataset';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './DataPipelineDatasetModal.module.scss';

const cx = classNames.bind(style);

// 학습 데이터 파이프라인의 데이터셋 생성 모달(modalType: CREATE_DP_DATASET).
//
// 플랫폼 드라이브의 데이터셋 모달(components/Modal/DatasetFormModal, CREATE_DATASET)과는
// 다른 물건이다. 그쪽은 원본 파일을 담는 드라이브 데이터셋이고, 이쪽은 그 원본을 받아
// 학습셋을 만들어 내는 파이프라인(jonathan_llm.llm_dp_dataset)이다. 이름이 비슷해
// 헷갈리기 쉬워 파일명과 modalType 을 둘 다 갈라 두었다.

const NAME_MAX = 128;
const DESC_MAX = 1000;

// 프리셋은 노드 체인을 정한다. 생성 시점에만 정할 수 있다 — BE 가 저장 단계에서
// 프리셋 변경을 거부한다(replace_flow).
const PRESET_OPTIONS = [
  { label: '범용', value: 'generic' },
  { label: '해양 COLREG', value: 'sds_colreg' },
];

function DataPipelineDatasetModal({ data, type }) {
  const { t } = useTranslation();
  const { workspace_id: workspaceId, handleRefresh, onCreated } = data;

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [preset, setPreset] = useState('generic');

  const validate = !!name.trim();

  // 프레임 계약: truthy 를 돌려주면 프레임이 모달을 닫고, falsy 면 버튼을 되살린다.
  const handleSubmit = async () => {
    const res = await createDataset({
      workspace_id: Number(workspaceId),
      name: name.trim(),
      // 빈 문자열을 보내면 '설명을 지웠다'는 뜻이 되므로 안 쓴 경우는 아예 보내지 않는다.
      description: description.trim() || null,
      preset,
    });
    if (res.status !== STATUS_SUCCESS) {
      // 이름 중복이면 BE 가 사유를 문장으로 준다 — 그대로 보여줘야 사용자가 고칠 수 있다.
      errorToastMessage(res.error, res.message);
      return false;
    }
    handleRefresh?.();
    onCreated?.(res.result);
    return true;
  };

  return (
    <NewStyleModalFrame
      submit={{ text: t('create.label'), func: handleSubmit }}
      cancel={{ text: t('cancel.label') }}
      type={type}
      validate={validate}
      title='새 데이터셋'
      headerTitle='새 데이터셋'
      submitBtnTestId='create-dp-dataset-btn'
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel labelText='이름' labelSize='large' disableErrorMsg>
            <InputText
              size='medium'
              placeholder='데이터셋 이름 (워크스페이스 안에서 고유해야 합니다)'
              name='name'
              value={name}
              onChange={(e) => setName(e.target.value)}
              onClear={() => setName('')}
              options={{ maxLength: NAME_MAX }}
              autoFocus
              disableLeftIcon
              testId='dp-dataset-name-input'
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>

        <div className={cx('row')}>
          <InputBoxWithLabel labelText='설명' labelSize='large' disableErrorMsg>
            <Textarea
              size='large'
              placeholder='어떤 학습셋을 만들 데이터셋인지 (선택)'
              name='description'
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              options={{ maxLength: DESC_MAX }}
              isShowMaxLength
              customStyle={{ fontSize: '14px', height: '104px' }}
            />
          </InputBoxWithLabel>
        </div>

        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText='파이프라인 프리셋'
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              name='preset'
              value={preset}
              options={PRESET_OPTIONS}
              onChange={(e) => setPreset(e.target.value)}
              // 라벨이 i18n 키가 아니라 한글 문구다. 기본값(true)이면 t() 를 거쳐
              // 키를 못 찾은 문구가 그대로 나오거나 비어 보인다.
              isTranLabel={false}
              isLabelColor
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </NewStyleModalFrame>
  );
}

export default DataPipelineDatasetModal;
