import { useEffect, useRef } from 'react';

// Components
import Card from './Card';
import { InputText } from '@tango/ui-react';

// CSS Module
import style from './CardList.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const CardList = ({
  builtInType,
  jobGroupOptions,
  modelOptions,
  model,
  selectBuiltInModelHandler,
  thumbnailList,
  readOnly,
  onSearch,
  scroll,
  t,
}) => {
  const scrollRef = useRef();
  const isMount = useRef(true);

  const scrollHandler = (id) => {
    setTimeout(() => {
      scrollRef.current?.scrollTo(scrollRef.current, id * 90, 600);
    }, 500);
  };
  useEffect(() => {
    if (model && scroll && isMount.current) {
      modelOptions.forEach((option, idx) => {
        if (option?.id === model?.id) {
          scrollHandler(idx);
        }
      });
    }
    return () => {
      if (modelOptions?.length > 0) {
        isMount.current = false;
      }
    };
  }, [model, modelOptions, scroll]);

  return (
    <>
      <div className={cx('search-box')}>
        {builtInType && (
          <InputText
            type='medium'
            placeholder={t('search.placeholder')}
            leftIcon='/images/icon/ic-search.svg'
            disableLeftIcon={false}
            disableClearBtn={true}
            onChange={onSearch}
            customStyle={{ width: '100%' }}
          />
        )}
      </div>
      {builtInType ? (
        <ul
          className={cx('card-list', !jobGroupOptions && 'no-margin')}
          data-testid='model-list'
          ref={scrollRef}
        >
          {modelOptions.map((m, key) => {
            return (
              <Card
                {...m}
                key={key}
                idx={key}
                model={model}
                selectBuiltInModelHandler={selectBuiltInModelHandler}
                // readOnly={readOnly}
                readOnly={true}
                disabled={true} // TEST로 임시 dsiabeld
                modelOptions={modelOptions}
                thumbnailList={thumbnailList}
                scroll={scroll}
              />
            );
          })}
        </ul>
      ) : (
        <div className={cx('placeholder')}>
          {t('modelSelect.step2.placeholder')}
        </div>
      )}
    </>
  );
};
export default CardList;
