import { useSelector } from 'react-redux';

import DownloadProgress from '@src/components/molecules/DownloadProgress/DownloadProgress';

function DownloadProgressContainer() {
  const { downloadProgress, isOpen } = useSelector((state) => state.download);
  return isOpen ? (
    <DownloadProgress downloadProgress={downloadProgress} />
  ) : null;
}
export default DownloadProgressContainer;
