import Card from './Card';
import CardList from './CardList';
import CreateCard from './CreateCard';

const CardTemplate = ({
  createLabel,
  cardItems,
  handleCreateCard,
  handleOnClickCard,
  handleBookMark,
  handleDelete,
  handleEdit,
  width,
  height = 340,
}) => {
  return (
    <CardList>
      <CreateCard
        label={createLabel}
        handleCreateCard={handleCreateCard}
        width={width}
        height={height}
      />
      {cardItems.map((cardInfo, idx) => {
        const {
          id,
          title,
          subTitle,
          constructor,
          updateTime,
          createTime,
          isAccess,
          status,
        } = cardInfo;
        return (
          <Card
            key={id ?? idx}
            id={id}
            title={title}
            subTitle={subTitle}
            constructor={constructor}
            updateTime={updateTime}
            createTime={createTime}
            status={status}
            userList={cardInfo?.userList}
            isAccess={isAccess}
            isBookMark={cardInfo?.isBookMark}
            handleBookMark={handleBookMark}
            handleOnClickCard={handleOnClickCard}
            handleDelete={handleDelete}
            handleEdit={handleEdit}
            width={width}
            height={height}
          />
        );
      })}
    </CardList>
  );
};

export default CardTemplate;
