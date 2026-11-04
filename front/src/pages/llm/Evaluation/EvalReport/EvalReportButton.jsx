import { useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import EvalReportModal from './EvalReportModal';

// 평가 리포트 내보내기 버튼 — projectId 를 주면 프로젝트(실행 전체 요약), 아니면 실행 1건.
// 실행 1건은 정답 대조·의도/슬롯(결과 페이지 헤더)·LLM 심사(프로젝트
// 상세)·전문가(채점 진행 헤더)가 같이 쓴다. 모달은 body 로 띄운다 — 전문가 화면은 버튼이
// sticky 헤더 안에 있어, 제자리에 두면 그 헤더의 쌓임 맥락에 갇힌다.
const EvalReportButton = ({
  modelId,
  jobId,
  projectId,
  disabled = false,
  size = 'l',
}) => {
  const missingTarget =
    projectId == null && (modelId == null || !jobId);
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <>
      <ButtonV2
        type='outline'
        colorType='gray'
        size={size}
        label={t('evaluation.report.export')}
        disabled={disabled || missingTarget}
        // 왜 잠겼는지 알린다(전문가 진행 헤더의 nextBlocked 와 같은 방식).
        title={
          disabled && projectId == null
            ? t('evaluation.report.disabledHint')
            : undefined
        }
        onClick={() => setOpen(true)}
      />
      {open &&
        createPortal(
          <EvalReportModal
            modelId={modelId}
            jobId={jobId}
            projectId={projectId}
            onClose={close}
          />,
          document.body,
        )}
    </>
  );
};

export default EvalReportButton;
