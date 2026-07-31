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
  statusBadge = false,
  // opt-in — 접근 불가(isAccess===0) 카드를 회색+클릭불가로 표시한다.
  // isAccess 의 의미가 소비처마다 달라(Model=계산된 접근가능, Rag/Prompt=원시 access)
  // 기본 false. 계산된 접근 가능 여부를 넘기는 화면(Model)만 켠다.
  disableNoAccess = false,
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
          typeBadge,
          kind,
          qualifierBadge,
          qualifierBadgeKind,
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
            statusBadge={statusBadge}
            noAccess={disableNoAccess && isAccess === 0}
            typeBadge={typeBadge}
            typeBadgeKind={kind}
            qualifierBadge={qualifierBadge}
            qualifierBadgeKind={qualifierBadgeKind}
          />
        );
      })}
    </CardList>
  );
};

export default CardTemplate;
