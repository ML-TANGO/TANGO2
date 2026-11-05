import { useSelector } from 'react-redux';

// Components
import UploadListModal from '@src/modals/UploadListModal';

/**
 * 파일 업로드 현황 모달 컴포넌트를 감싸는 컨테이너
 *
 * upload store에서 isOpen값이 true면 모달 제공해주는 기능
 *
 * Frame 컴포넌트에서 사용 중
 * @returns
 */
function UploadListContainer() {
  const { isOpen } = useSelector((state) => state.upload);
  if (isOpen) return <UploadListModal />;
  return null;
}

export default UploadListContainer;
