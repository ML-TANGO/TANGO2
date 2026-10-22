// 평가 리포트 인쇄(PDF 저장) — 미리보기에 그려진 HTML 을 빈 iframe 에 옮겨 인쇄한다.
// 앱 화면(사이드바·헤더)과 스타일이 섞이지 않고, 한글은 사용자 PC 의 글꼴로 나온다.
// 서버에서 PDF 를 만들지 않는 이유는 평가 이미지에 한글 폰트·PDF 라이브러리가 없어서다.

const PRINT_CSS = `
@page { size: A4; margin: 16mm 14mm; }
body {
  margin: 0;
  color: #111;
  font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
h1 { font-size: 18pt; margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid #222; }
h2 { font-size: 14pt; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #bbb; }
h3 { font-size: 12pt; margin: 16px 0 6px; }
h4 { font-size: 11pt; margin: 12px 0 4px; }
h1, h2, h3, h4 { page-break-after: avoid; }
table { width: 100%; margin: 8px 0; border-collapse: collapse; font-size: 9.5pt; }
th, td { padding: 4px 6px; border: 1px solid #bbb; text-align: left; vertical-align: top; word-break: break-word; }
th { background: #f0f0f0; }
tr { page-break-inside: avoid; }
pre {
  margin: 4px 0 8px;
  padding: 6px 8px;
  border: 1px solid #ddd;
  background: #f6f6f6;
  font-size: 9pt;
  white-space: pre-wrap;
  word-break: break-word;
}
code { font-family: D2Coding, Consolas, monospace; }
blockquote { margin: 8px 0; padding: 4px 10px; border-left: 3px solid #999; color: #444; }
`;

const escapeHtml = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ],
  );

// html 은 react-markdown 이 그린 미리보기 DOM 의 innerHTML 이다(원문 HTML 은 렌더하지 않는다).
// title 은 인쇄 창이 PDF 파일 이름으로 제안하는 값이다.
export const printReportHtml = (html, title) => {
  const frame = document.createElement('iframe');
  frame.setAttribute('aria-hidden', 'true');
  frame.style.cssText =
    'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
  document.body.appendChild(frame);

  const win = frame.contentWindow;
  const doc = win.document;
  doc.open();
  // CSP 는 방어선을 하나 더 두는 것이다 — 이 iframe 은 앱과 같은 출처라, 만에 하나 스크립트가
  // 섞여 들어와도 실행되지 않게 한다(인라인 <style> 만 허용).
  doc.write(
    `<!doctype html><html lang="ko"><head><meta charset="utf-8">` +
      `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">` +
      `<title>${escapeHtml(title)}</title><style>${PRINT_CSS}</style></head><body>${html}</body></html>`,
  );
  doc.close();

  // 인쇄 창이 닫힌 뒤 지운다. Chrome 은 print() 가 창이 닫힐 때까지 멈추지만 Firefox 는 바로
  // 돌아오므로, afterprint 를 못 받는 경우를 위한 시간 상한을 넉넉히 둔다.
  let timer = null;
  const cleanup = () => {
    clearTimeout(timer);
    frame.remove();
  };
  win.addEventListener('afterprint', cleanup, { once: true });
  timer = setTimeout(cleanup, 10 * 60 * 1000);
  win.focus();
  win.print();
};
