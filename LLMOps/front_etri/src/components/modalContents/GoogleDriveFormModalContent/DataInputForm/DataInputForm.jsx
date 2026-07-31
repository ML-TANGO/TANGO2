// Atoms
import GoogleDrive from '@src/components/atoms/GoogleDrive';

/**
 * 데이터셋 Google Drive 폼에서 사용되는 필수입력 폼 컴포넌트
 * @param {{ inputHandler: Function }} props
 * @returns
 */
function DataInputForm({ inputHandler }) {
  return (
    <>
      <GoogleDrive onChange={inputHandler} />
    </>
  );
}

export default DataInputForm;
