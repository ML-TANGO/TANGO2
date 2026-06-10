// CSS Module
import classNames from 'classnames/bind';
import style from './GroupList.module.scss';
const cx = classNames.bind(style);

function GroupList({
  onClickNoGroup,
  noGroupSelectedStatus,
  groupData,
  clickedDataList,
  onClickGroupList,
  t,
}) {
  return (
    <>
      <div
        onClick={() => onClickNoGroup()}
        className={cx(noGroupSelectedStatus && 'clicked-group', 'group-list')}
      >
        <div className={cx('name-desc')}>
          <span className={cx('name')}>{t('template.ungrouped.label')}</span>
        </div>
      </div>
      {groupData?.map((data) => {
        return (
          <div
            key={data.id}
            onClick={() => onClickGroupList(data)}
            className={cx(
              !noGroupSelectedStatus &&
                clickedDataList?.id === data.id &&
                'clicked-group',
              'group-list',
            )}
          >
            <div className={cx('name-desc')}>
              <span className={cx('name')}>{data.name}</span>
              {data.description && (
                <span className={cx('desc')}>{data.description}</span>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}
export default GroupList;
