// Components
import Loading from '@src/components/atoms/loading/Loading';

import DeferredComponent from '@src/hooks/useDeferredComponent';

import CardList from './CardList';
import ListFilter from './ListFilter';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserTrainingContent.module.scss';

const cx = classNames.bind(style);

/**
 * 학습 목록 페이지 컴포넌트
 * @param {{
 *  watchFilterViewType: ({ filter, viewType }) => {}
 *  trainingList: [{}],
 *  selectedViewType: 'CARD_VIEW' | 'TABLE_VIEW',
 *  isLoading: boolean,
 *  openCreateTrainingModal: Function,
 *  refreshData: Function,
 * }}
 * @component
 * @example
 *
 * const watchFilterViewType = ({ filter, viewType }) => {};
 *
 * const openCreateTrainingModal = () => {
 *  // Open training modal...
 * };
 *
 * const refreshData = () => {
 *   // refresh data
 * }
 *
 * return (
 *    <UserTrainingContent
 *      watchFilterViewType={watchFilterViewType}
 *      selectedViewType='CARD_VIEW'
 *      isLoading={isLoading}
 *      openCreateTrainingModal={openCreateTrainingModal]}
 *      refreshData={refreshData}
 *    />
 * )
 *
 *
 *
 * -
 */
function UserTrainingContent({
  watchFilterViewType,
  trainingList,
  selectedViewType,
  isLoading,
  openCreateTrainingModal,
  refreshData,
}) {
  return (
    <div className={cx('training-list-page', isLoading && 'loading-wrapper')}>
      {/* 제목 및 필터 영역 */}
      <ListFilter
        watchFilterViewType={watchFilterViewType}
        selectedViewType={selectedViewType}
        onCreate={openCreateTrainingModal}
      />
      {/* 리스트 영역 */}
      {isLoading ? (
        <div className={cx('loading-box')}>
          <DeferredComponent>
            <Loading />
          </DeferredComponent>
        </div>
      ) : (
        selectedViewType === 'CARD_VIEW' && (
          <CardList
            trainingList={trainingList}
            isLoading={isLoading}
            onClickCard={openCreateTrainingModal}
            refreshData={refreshData}
          />
        )
      )}
    </div>
  );
}

export default UserTrainingContent;
