import { useSelector } from 'react-redux';

// Components
import ProgressStatusList from '@src/components/molecules/ProgressStatusList';

function ProgressStatusListContainer() {
  const { progressList, isOpen } = useSelector((state) => state.progressList);
  return <>{isOpen && <ProgressStatusList progressList={progressList} />}</>;
}

export default ProgressStatusListContainer;
