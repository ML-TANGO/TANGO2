// Components
import Card from './Card';
// import CardLoading from './CardLoading';
import CreateCard from './CreateCard';

// CSS Module
import classNames from 'classnames/bind';
import style from './CardList.module.scss';

const cx = classNames.bind(style);

// const loadingList = [{}, {}, {}, {}, {}, {}, {}];
/**
 * 배포 카드 목록 컴포넌트
 * @param {{ deploymentList: Array, isLoading: boolean, onClickCard: Function, refreshData: Function }}
 * @component
 * @example
 *
 * const deploymentList = [];
 * let isLoading = false;
 * const onClickCard = () => {};
 *
 * return (
 *    <CardList isLoading={isLoading} onClickCard={onClickCard} />
 * );
 *
 *
 * -
 */
function CardList({ deploymentList = [], onClickCard, refreshData }) {
  return (
    <div className={cx('card-list')}>
      {onClickCard && <CreateCard onClick={onClickCard} />}
      {Array.isArray(deploymentList) && deploymentList.map((data, key) => (
        <Card data={data} key={key} refreshData={refreshData} />
      ))}
    </div>
  );
}

export default CardList;
