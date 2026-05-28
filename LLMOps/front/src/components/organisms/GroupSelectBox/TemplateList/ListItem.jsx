// Components
import ListInfo from '@src/components/pageContents/user/UserDeploymentContent/Template/List/ListInfo';

// Icons
import WarningIcon from '@src/static/images/icon/ic-warning-red.svg';

// CSS module
import style from './TemplateList.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function List({ data, type, clickedTemplateLists, onClickTemplateList }) {
  return (
    <div className={cx('template-list')}>
      <div
        onClick={() => onClickTemplateList(data)}
        className={cx(
          clickedTemplateLists?.id === data.id &&
            'active-template-list-container',
          'template-list-container',
        )}
      >
        <div className={cx('name-desc')}>
          {data.item_deleted?.length > 0 && (
            <span className={cx('error')}>
              <img src={WarningIcon} alt='error' />
            </span>
          )}
          <span className={cx('name')}>{data.name}</span>
          {data.description && (
            <span className={cx('desc')}>{data.description}</span>
          )}
        </div>
      </div>
      <div
        className={cx(
          clickedTemplateLists?.id === data.id &&
            type !== 'template' &&
            'clicked-template-list-detail',
          'template-list-detail',
        )}
      >
        {clickedTemplateLists?.id === data.id && (
          <ListInfo data={data} clickedTemplateLists={clickedTemplateLists} />
        )}
      </div>
    </div>
  );
}
export default List;
