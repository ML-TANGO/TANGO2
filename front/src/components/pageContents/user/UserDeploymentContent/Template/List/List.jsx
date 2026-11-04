import { useEffect, useState } from 'react';

// Components
import { Button } from '@jonathan/ui-react';
import ListItem from './ListItem';

// Icons
import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';
import DeleteIcon from '@src/static/images/icon/00-ic-basic-delete.svg';

// CSS module
import style from './List.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function List({
  groupList,
  templateData,
  onClickGroupList,
  clickedGroupId,
  onClickEditTemplate,
  deleteGroupHandler,
  editGroupHandler,
  deleteTemplateHandler,
  onClickNoGroup,
  noGroupSelectedStatus,
  scrollY,
  t,
}) {
  const [clickedTemplateLists, setClickedTemplateLists] = useState([]);

  const onClickTemplate = (data) => {
    if (clickedTemplateLists.includes(data.id)) {
      setClickedTemplateLists(
        clickedTemplateLists.filter((idx) => idx !== data.id),
      );
    } else {
      setClickedTemplateLists((prev) => [...prev, data.id]);
    }
  };

  useEffect(() => {
    setClickedTemplateLists(() => [...new Array(0)]);
  }, [templateData]);

  return (
    <>
      {groupList && (
        <>
          <div
            className={cx('main-container')}
            onClick={() => onClickNoGroup()}
          >
            <div className={cx(noGroupSelectedStatus && 'active', 'container')}>
              <div className={cx('title-container')}>
                {t('template.ungrouped.label')}
              </div>
            </div>
          </div>
          {groupList?.map((data) => {
            return (
              <div className={cx('main-container')} key={data.id}>
                <div
                  className={cx(
                    !noGroupSelectedStatus &&
                      clickedGroupId === data.id &&
                      data.description &&
                      'description-active',
                    !noGroupSelectedStatus &&
                      clickedGroupId === data.id &&
                      (data.description === '' || data.description === null) &&
                      'active',
                    'container',
                  )}
                >
                  <div
                    className={cx('title-container')}
                    onClick={() => onClickGroupList(data)}
                  >
                    <div className={cx('sub-container')}>
                      <div className={cx('title')} title={data.name}>
                        <span className={cx('name')}>{data.name}</span>
                        <span className={cx('description')}>
                          {data.description}
                        </span>
                      </div>
                      <div className={cx('user')}>{data.user_name}</div>
                    </div>
                  </div>
                  <div className={cx('button-container')}>
                    <div className={cx('modify-btn')}>
                      <Button
                        type='primary-reverse'
                        size='x-small'
                        customStyle={{
                          width: '20px',
                          background: 'transparent',
                          border: '0px',
                        }}
                        onClick={() => editGroupHandler(data)}
                        disabled={data.permission_level > 3 ? true : false}
                      >
                        <img
                          className={cx(
                            data.permission_level > 3 && 'disable-image',
                          )}
                          src={EditIcon}
                          alt='edit'
                        />
                      </Button>
                    </div>
                    <div className={cx('delete-btn')}>
                      <Button
                        type='primary-reverse'
                        size='x-small'
                        customStyle={{
                          width: '20px',
                          background: 'transparent',
                          border: '0px',
                        }}
                        onClick={() => deleteGroupHandler(data)}
                        disabled={data.permission_level > 3 ? true : false}
                      >
                        <img
                          className={cx(
                            data.permission_level > 3 && 'disable-image',
                          )}
                          src={DeleteIcon}
                          alt='delete'
                        />
                      </Button>
                    </div>
                  </div>
                </div>
                <div
                  className={cx(
                    !noGroupSelectedStatus &&
                      clickedGroupId === data.id &&
                      data.description &&
                      'group-description',
                    'inactive-description',
                  )}
                >
                  <div>
                    <p className={cx('description')}>{data.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </>
      )}
      {templateData?.map((data) => {
        return (
          <ListItem
            key={data.id}
            data={data}
            clickedTemplateLists={clickedTemplateLists}
            onClickTemplate={onClickTemplate}
            onClickEditTemplate={onClickEditTemplate}
            deleteTemplateHandler={deleteTemplateHandler}
            scrollY={scrollY}
          />
        );
      })}
    </>
  );
}
export default List;
