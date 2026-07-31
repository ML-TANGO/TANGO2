import { useHistory } from 'react-router-dom';

// Components
import AdminRecordContent from '@src/components/pageContents/admin/AdminRecordContent';

function AdminRecordPage() {
  const history = useHistory();

  /**
   * 기록 상세 화면으로 이동
   *
   * @param {number} workspaceId 워크스페이스 ID
   */
  const moveToDetailPage = (workspaceId) => {
    history.push(`/admin/records/detail/${workspaceId}`);
  };

  return <AdminRecordContent moveToDetailPage={moveToDetailPage} />;
}

export default AdminRecordPage;
