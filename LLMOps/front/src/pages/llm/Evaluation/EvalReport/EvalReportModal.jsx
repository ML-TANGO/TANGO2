import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Loading } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';

import { getEvalReport } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import { printReportHtml } from './printReport';

import classNames from 'classnames/bind';
import style from './EvalReport.module.scss';

const cx = classNames.bind(style);

// 평가 실행 1건 리포트 미리보기 — 서버가 만든 Markdown 을 그대로 보이고, 같은 텍스트를
// .md 로 내려받거나 인쇄 창(PDF 저장)으로 보낸다.
// 모델 출력·코멘트가 섞인 문서라 원문 HTML 은 렌더하지 않는다(rehype-raw 미사용). 리포트에는
// 이미지가 없으므로 img 도 막아 둔다 — 문서 속 링크가 외부로 요청을 보내지 못하게.
const EvalReportModal = ({ modelId, jobId, onClose }) => {
  const { t } = useTranslation();
  const [report, setReport] = useState(null); // { markdown, filename }
  const [loading, setLoading] = useState(true);
  const previewRef = useRef(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getEvalReport(modelId, jobId).then((res) => {
      if (!alive) return;
      if (res.status === STATUS_SUCCESS && res.result?.markdown) {
        setReport(res.result);
      } else {
        errorToastMessage(res.error, res.message);
      }
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [modelId, jobId]);

  // NewStyleModalFrame 은 Redux 모달 스택을 닫는데 이 모달은 로컬 상태로 뜬다 — Esc 를
  // capture 단계에서 가로채 이 모달만 닫는다(ExpertInferenceModal 과 같은 처방).
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key !== 'Escape') return;
      event.stopImmediatePropagation();
      onClose();
    };
    document.addEventListener('keydown', handleEscape, true);
    return () => document.removeEventListener('keydown', handleEscape, true);
  }, [onClose]);

  // 프레임이 마운트 때 건 body 스크롤 잠금을 언마운트에서 푼다(프레임에 복구가 없다).
  useEffect(
    () => () => {
      document.body.style.overflow = 'auto';
    },
    [],
  );

  const downloadMarkdown = () => {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([report.markdown], { type: 'text/markdown;charset=utf-8' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = report.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // 바로 회수하면 일부 브라우저(Safari·구 Firefox)가 다운로드를 취소한다.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const savePdf = () => {
    if (!report || !previewRef.current) return;
    printReportHtml(
      previewRef.current.innerHTML,
      report.filename.replace(/\.md$/, ''),
    );
  };

  return (
    <NewStyleModalFrame
      type='evalReportModal'
      title={t('evaluation.report.title')}
      cancel={{ text: 'close.label', func: onClose }}
      apply={
        report
          ? {
              text: 'evaluation.report.downloadMarkdown',
              func: downloadMarkdown,
            }
          : undefined
      }
      submit={{ text: 'evaluation.report.savePdf', func: savePdf }}
      validate={!!report}
      footerMessage={report ? t('evaluation.report.pdfHint') : ''}
      isResize
      isMinimize
      customStyle={{ width: '880px' }}
    >
      {loading && (
        <div className={cx('report-loading')}>
          <Loading />
        </div>
      )}
      {!loading && report && (
        <div ref={previewRef} className={cx('report')}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            disallowedElements={['img']}
            unwrapDisallowed
          >
            {report.markdown}
          </ReactMarkdown>
        </div>
      )}
      {!loading && !report && (
        <div className={cx('report-empty')}>{t('noData.message')}</div>
      )}
    </NewStyleModalFrame>
  );
};

export default EvalReportModal;
