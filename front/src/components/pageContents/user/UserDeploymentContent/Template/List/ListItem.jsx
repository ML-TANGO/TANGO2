import { useEffect, useState, useRef, useCallback } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, Tooltip } from '@jonathan/ui-react';
import ListInfo from './ListInfo';

// Icons
import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';
import DeleteIcon from '@src/static/images/icon/00-ic-basic-delete.svg';
import WarningIcon from '@src/static/images/icon/ic-warning-red.svg';

// CSS module
import style from './List.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function List({
  data,
  clickedTemplateLists,
  onClickTemplate,
  onClickEditTemplate,
  deleteTemplateHandler,
  scrollY,
}) {
  const { t } = useTranslation();
  const tooltipRef = useRef();

  const [x, setX] = useState();
  const [y, setY] = useState();

  // calculate X and Y
  const getPosition = useCallback(() => {
    if (tooltipRef.current) {
      const x = tooltipRef.current.offsetLeft;
      setX(x + 120);

      const y = tooltipRef.current.offsetTop - scrollY;
      setY(y + 24);
    }
  }, [scrollY]);

  useEffect(() => {
    getPosition();
  }, [getPosition, onClickTemplate]);

  return (
    <div className={cx('main-container')} key={data.id}>
      <div
        key={data.id}
        className={cx(
          clickedTemplateLists.includes(data.id) && 'template-active',
          'container',
        )}
      >
        <div
          onClick={() => onClickTemplate(data)}
          className={cx('title-container')}
        >
          <div className={cx('sub-container')}>
            <div className={cx('title')}>
              {data.item_deleted?.length > 0 && (
                <span className={cx('error')} ref={tooltipRef}>
                  <Tooltip
                    title={t('template.deployment.warning.Tooltip.message')}
                    contents={
                      <ul className={cx('error-list')}>
                        {data.item_deleted.map((item, idx) => (
                          <li key={idx}>{t(item)}</li>
                        ))}
                      </ul>
                    }
                    contentsAlign={{
                      vertical: 'bottom',
                      horizontal: 'center',
                    }}
                    customStyle={{
                      position: 'relative',
                      display: 'block',
                    }}
                    contentsCustomStyle={{
                      minWidth: '200px',
                      position: 'fixed',
                      top: y,
                      left: x,
                    }}
                    globalCustomStyle={{
                      position: 'relative',
                    }}
                  >
                    <img src={WarningIcon} alt='error' />
                  </Tooltip>
                </span>
              )}
              <span className={cx('name')}>{data.name}</span>
              <span className={cx('description')}>{data.description}</span>
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
              disabled={data.permission_level > 4 ? true : false}
              onClick={() => onClickEditTemplate(data)}
            >
              <img
                className={cx(data.permission_level > 4 && 'disable-image')}
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
              onClick={() => deleteTemplateHandler(data)}
              disabled={data.permission_level > 4 ? true : false}
            >
              <img
                className={cx(data.permission_level > 4 && 'disable-image')}
                src={DeleteIcon}
                alt='delete'
              />
            </Button>
          </div>
        </div>
      </div>
      <ListInfo data={data} clickedTemplateLists={clickedTemplateLists} />
    </div>
  );
}
export default List;
