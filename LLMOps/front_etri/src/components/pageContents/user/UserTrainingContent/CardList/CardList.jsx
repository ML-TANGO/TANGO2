// Components
import Card from './Card';
import CardLoading from './CardLoading';
import CreateCard from './CreateCard';

// CSS Module
import classNames from 'classnames/bind';
import style from './CardList.module.scss';

const cx = classNames.bind(style);

const loadingList = [{}, {}, {}, {}, {}, {}, {}];
/**
 * 학습 카드 목록 컴포넌트
 * @param {{ trainingList: Array, isLoading: boolean, onClickCard: Function, refreshData: Function }}
 * @component
 * @example
 *
 * const trainingList = [];
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
function CardList({ trainingList = [], isLoading, onClickCard, refreshData }) {
  return (
    <div className={cx('card-list', isLoading && 'loading')}>
      {onClickCard && <CreateCard onClick={onClickCard} />}

      {/* {isLoading
        ? loadingList.map((_, key) => <CardLoading key={key} />)
        : trainingList.map((data, key) => (
            <Card data={data} key={key} refreshData={refreshData} />
          ))} */}
      {trainingList.map((data, key) => (
        <Card data={data} key={key} refreshData={refreshData} />
      ))}
    </div>
  );
}

export default CardList;
