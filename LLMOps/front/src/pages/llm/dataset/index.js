// 학습 데이터 파이프라인 화면 배럴.
//
// UserRouter 의 routeArrAll 이 여기서 가져간다. 라우터가 페이지 파일 경로를 직접
// 알지 않게 해 두면 화면을 옮기거나 합쳐도 라우터를 건드리지 않는다.
export { default as DatasetListPage } from './DatasetListPage';
export { default as PipelinePage } from './PipelinePage';
export { default as StageConfigPage } from './StageConfigPage';
export { default as GeneratePage } from './GeneratePage';
export { default as GatePage } from './GatePage';
export { default as SdsNodePage } from './SdsNodePage';
export { default as ReviewPage } from './ReviewPage';
export { default as AnalysisPage } from './AnalysisPage';
export { default as ComposePage } from './ComposePage';
export { default as HistoryPage } from './HistoryPage';
export { default as RecordPage } from './RecordPage';
