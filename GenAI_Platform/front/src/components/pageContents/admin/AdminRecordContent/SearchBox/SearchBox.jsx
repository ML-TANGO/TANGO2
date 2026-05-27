import { useState } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './SearchBox.module.scss';
const cx = classNames.bind(style);

const SearchBox = ({
  children,
  onSearch,
  selectedList = [],
  removeChip,
  t,
}) => {
  const [expand, setExpand] = useState(false);

  const showHideHandler = () => {
    setExpand(!expand);
  };

  const paramObj = {};
  for (let i = 0; i < selectedList.length; i += 1) {
    const { key, value } = selectedList[i].param;
    const { label, value: orgValue } = selectedList[i].origin;
    if (!paramObj[key]) {
      paramObj[key] = [];
    }
    if (orgValue !== 'all') {
      if (key === 'workspaces' || key === 'training' || key === 'workspace')
        paramObj[key].push({ label, keyIndex: i });
      else paramObj[key].push({ label: value, keyIndex: i });
    }
  }
  const paramKeys = Object.keys(paramObj);
  return (
    <div className={cx('search-box')}>
      <div className={cx('select-area')}>
        {children}
        <Button
          type='secondary'
          size='medium'
          onClick={() => {
            onSearch();
            setExpand(true);
          }}
        >
          {t('search.label')}
        </Button>
      </div>
      {expand && (
        <div className={cx('chips-area')}>
          {paramKeys.map(
            (key, idx) =>
              paramObj[key].length !== 0 && (
                <span className={cx('param-group')} key={idx}>
                  <span className={cx('param-name')}>
                    {t(`${key}.label`)} :{' '}
                  </span>
                  {paramObj[key].map((v, idx2) =>
                    v.label.toString().toLowerCase() !== 'all' ? (
                      <span key={idx2} className={cx('chip')}>
                        {v.label}
                        <i
                          className={cx('remove-btn')}
                          onClick={() => {
                            removeChip(v.keyIndex);
                          }}
                        >
                          <img
                            src='/images/icon/close-s.svg'
                            alt='close icon'
                          />
                        </i>
                      </span>
                    ) : (
                      <span key={idx2}></span>
                    ),
                  )}
                </span>
              ),
          )}
        </div>
      )}
      {paramKeys.length > 0 && (
        <div
          className={cx('show-more-area')}
          style={{ marginTop: !expand ? '20px' : '0px' }}
        >
          <button className={cx('show-more-btn')} onClick={showHideHandler}>
            <img
              src='/images/icon/angle-up.svg'
              className={cx(!expand && 'hide')}
              alt='show/hide button'
            />
          </button>
        </div>
      )}
    </div>
  );
};

export default withTranslation()(SearchBox);
