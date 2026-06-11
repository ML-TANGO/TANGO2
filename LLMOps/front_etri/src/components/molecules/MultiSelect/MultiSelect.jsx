// Components
import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import { Badge, Button } from '@tango/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './MultiSelect.module.scss';

const cx = classNames.bind(style);

const asc = (list, key) => list.sort((a, b) => a[key] - b[key]);

function MultiSelect({
  label,
  listLabel,
  selectedLabel,
  list: initList,
  selectedList: initSelectedList = [],
  onChange,
  exceptItem,
  error,
  optional,
  readOnly,
  placeholder,
  innerRef,
  ...rest
}) {
  const { t } = useTranslation();
  const scrollRef = useRef();
  const selectedScrollRef = useRef();
  const [datas, setDatas] = useState({
    list: initList,
    selectedList: initSelectedList,
  });
  const [userList, setUserList] = useState([]);
  const [selectedUserList, setSelectedUserList] = useState([]);
  const [userSearchList, setUserSearchList] = useState([]);
  const [selectedUserSearchList, setSelectedUserSearchList] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [selectedInputValue, setSelectedInputValue] = useState('');

  const [filteredArr, setFilteredArr] = useState([]);
  const [filterSelectedArr, setFilteredSelectedArr] = useState([]);

  const [filterIndex, setFilterIndex] = useState({
    all: 0,
    curr: 0,
  });
  const [filterSelectedIndex, setFilterSelectedIndex] = useState({
    all: 0,
    curr: 0,
  });

  const [click, setClick] = useState(false);
  const [token, setToken] = useState(false);

  // 아이템 선택 이벤트
  const onSelectItem = (idx, target) => {
    const { list, selectedList } = datas;
    const targetList = target === 'list' ? [...list] : [...selectedList];
    const { selected } = targetList[idx];
    targetList[idx].selected = !selected;
    setDatas({
      ...datas,
      [target]: targetList,
    });
  };

  const filterFitValue = (list, label, value) => {
    const t = list
      .map((d, idx) => {
        if (d.label === label && d.value === value) {
          return idx;
        }
        return undefined;
      })
      .filter((e) => e !== undefined);
    return t[0];
  };

  const filterFirstValue = (list, label) => {
    return list
      .map((d, idx) => {
        if (d.label.includes(label)) {
          return idx;
        }
        return undefined;
      })
      .filter((e) => e !== undefined)[0];
  };

  // 선택된 아이템 추가
  const addSelectedItem = () => {
    setClick(false);
    const { list: prevList, selectedList: prevSelectedList } = datas;
    const list = prevList.filter(({ selected }) => !selected);
    const selectedList = prevList
      .filter(({ selected }) => selected)
      .map((user) => ({ ...user, selected: false }));
    if (selectedList.length === 0) return;
    setDatas({
      ...datas,
      list: asc(list, 'idx'),
      selectedList: asc([...prevSelectedList, ...selectedList], 'idx'),
    });
  };

  // 모든 아이템 추가
  const addAllItem = () => {
    setClick(false);
    const disabledData = datas.list.filter(
      (listItem) => listItem.deleteDisable === true,
    );
    const prevData = datas.list.filter(
      (listItem) => listItem.deleteDisable !== true,
    );

    const { list: prevList, selectedList: prevSelectedList } = datas;
    const selectedList = asc(
      [...prevData, ...prevSelectedList].map((item) => ({
        ...item,
        selected: false,
      })),
      'idx',
    );
    if (prevList.length === 0) return;
    setDatas({
      ...datas,
      selectedList,
      list: disabledData,
    });
  };

  // 선택된 아이템 삭제
  const removeSelectedItem = () => {
    setClick(false);
    const { list: prevList, selectedList: prevSelectedList } = datas;
    const selectedList = prevSelectedList.filter(({ selected }) => !selected);
    const list = prevSelectedList
      .filter(({ selected }) => selected)
      .map((user) => ({ ...user, selected: false }));
    if (list.length === 0) return;
    setDatas({
      ...datas,
      list: asc([...list, ...prevList], 'idx'),
      selectedList: asc(selectedList, 'idx'),
    });
  };

  // 모든 선택된 아이템 삭제
  const removeAllSelectedItem = () => {
    setClick(false);
    const disabledData = datas.selectedList.filter(
      (listItem) => listItem.deleteDisable === true,
    );
    const prevData = datas.selectedList.filter(
      (listItem) => listItem.deleteDisable !== true,
    );

    const { list: prevList, selectedList: prevSelectedList } = datas;
    if (prevSelectedList.length === 0) return;
    const list = asc(
      [...prevList, ...prevData].map((user) => ({
        ...user,
        selected: false,
      })),
      'idx',
    );

    setDatas({
      ...datas,
      list,
      selectedList: disabledData,
    });
  };

  const { list, selectedList } = datas;

  /**
   * 글자 하이라이트 핸들러
   * @returns html
   */
  const highlightString = () => {
    const findMatchingWords = (word, target) => {
      // word -> 전체 텍스트
      // target -> event.taget.value
      const result = [];
      word?.forEach((list) => {
        // 들어온 value 맵 돌면서 전체 텍스트에 포함되어있는지
        if (list.label?.includes(target)) {
          // 포함되어 있다면 result에 넣기
          result.push(list);
        }
      });
      return result;
    };

    const highlight = (word, target, Datalist) => {
      const matchingWords = findMatchingWords(word, target);
      const idxArr = []; // Number
      const result = []; // any
      let i = 0;
      Datalist.forEach((alph, idx) => {
        // 위 함수에 의해서 리턴된 배열
        if (i < matchingWords.length) {
          if (
            alph.label === matchingWords[i].label &&
            alph.value === matchingWords[i].value
          ) {
            idxArr.push(idx);
            i++;
          }
        }
      });
      word?.forEach((alph, idx) => {
        if (idxArr.includes(idx)) {
          let targetText = target;
          let pullText = alph.label;
          let index = pullText.indexOf(targetText);
          const prevText = pullText.slice(0, index);
          const nextText = pullText.slice(index + targetText.length);
          let backgroundColor = '#c8dbfd';

          return result.push(
            <>
              {prevText}
              <span style={{ backgroundColor }} key={idx}>
                {targetText}
              </span>
              {nextText}
            </>,
          );
        } else result.push(<span key={idx}>{alph.label}</span>);
      });
      return result;
    };

    return highlight;
  };

  /**
   *  input 핸들러
   * @param {String} value
   * @returns
   */
  const searchInputHandler = useCallback(
    (value) => {
      setInputValue(value);
      const first = filterFirstValue(datas.list, value);
      if (value !== '' && filteredArr.length < 1 && !click) {
        scrollRef.current[first]?.scrollIntoView();
      }

      if (value === '') {
        setUserSearchList([]);
        setClick(false);
        setFilterIndex({ ...filterIndex, curr: 0, token: false });
        // token false로 둬야 첫화면에서 아래로 내려가지 않음
        setFilteredArr([]);

        if (scrollRef.current && token) {
          scrollRef.current[first]?.scrollIntoView();
        }

        return null;
      } else {
        setToken(true);
      }

      const highlightHandler = highlightString();
      const result = highlightHandler(userList, value, datas.list);

      setUserSearchList(result);

      const filteredList = datas?.list.filter(
        (item) => item.label.includes(value) && exceptItem !== item.value,
      );

      if (filteredList.length > 0) {
        if (click) {
          setClick(false);
          const highlightHandler = highlightString();
          const result = highlightHandler(userList, inputValue, datas.list);
          setUserSearchList(result);
          return null;
        }

        setFilteredArr(filteredList);
        scrollRef.current[first]?.scrollIntoView();
        const newFilterIndex = {
          all: filteredList.length,
          curr: 1,
          token: true,
        };
        const highlightHandler = highlightString();

        const result = highlightHandler(userList, inputValue, datas.list);
        setUserSearchList(result);
        setFilterIndex(newFilterIndex);
      } else {
        setClick(false);
        setFilteredArr([]);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      datas,
      click,
      filterIndex,
      filteredArr.length,
      inputValue,
      token,
      userList,
      exceptItem,
    ],
  );

  const searchSelectedInputHandler = (value) => {
    setSelectedInputValue(value);
    const first = filterFirstValue(datas.selectedList, value);
    if (value !== '' && filteredArr.length < 1 && !click) {
      selectedScrollRef.current[first]?.scrollIntoView();
    }

    if (value === '') {
      setSelectedUserSearchList([]);
      setClick(false);
      setFilterSelectedIndex({ ...filterSelectedIndex, curr: 0, token: false });
      // token false로 둬야 첫화면에서 아래로 내려가지 않음
      setFilteredSelectedArr([]);

      if (selectedScrollRef.current && token) {
        selectedScrollRef.current[first]?.scrollIntoView();
      }

      return null;
    } else {
      setToken(true);
    }
    const highlightHandler = highlightString();
    const result = highlightHandler(
      selectedUserList,
      value,
      datas.selectedList,
    );

    setSelectedUserSearchList(result);

    const filteredList = datas?.selectedList.filter(
      (item) => item.label.includes(value) && exceptItem !== item.value,
    );

    if (filteredList.length > 0) {
      if (click) {
        setClick(false);
        const highlightHandler = highlightString();
        const result = highlightHandler(
          selectedUserList,
          value,
          datas.selectedList,
        );
        setSelectedUserSearchList(result);
        return null;
      }

      setFilteredSelectedArr(filteredList);
      selectedScrollRef.current[first]?.scrollIntoView();
      const newFilterIndex = {
        all: filteredList.length,
        curr: 1,
        token: true,
      };
      const highlightHandler = highlightString();
      const result = highlightHandler(
        selectedUserList,
        value,
        datas.selectedList,
      );

      setSelectedUserSearchList(result);
      setFilterSelectedIndex(newFilterIndex);
    } else {
      setClick(false);
      setFilteredSelectedArr([]);
    }
  };

  /**
   * 엔터 눌렀을 때 밑으로 스크롤 이동 핸들러
   * @param {Object} e
   */
  const onKeyPressHandler = (flag, e) => {
    const filterArr = flag ? filteredArr : filterSelectedArr;
    if (e.key === 'Enter' && filterArr.length > 0) {
      const dataList = flag ? datas.list : datas.selectedList;
      const filterIdx = flag ? filterIndex : filterSelectedIndex;

      const filteredNextValue = filterFitValue(
        dataList,
        filterArr[filterIdx.curr === filterArr.length ? 0 : filterIdx.curr]
          .label,
        filterArr[filterIdx.curr === filterArr.length ? 0 : filterIdx.curr]
          .value,
      );
      if (flag) {
        scrollRef.current[filteredNextValue]?.scrollIntoView();
      } else {
        selectedScrollRef.current[filteredNextValue]?.scrollIntoView();
      }
      const newFilterIndex = {
        all: filterIdx.all,
        curr: filterIdx.curr < filterArr.length ? filterIdx.curr + 1 : 1,
        token: true,
      };
      if (flag) setFilterIndex(newFilterIndex);
      else setFilterSelectedIndex(newFilterIndex);
    }
  };

  // 초기 목록 및 선택 목록 설정 라이프 사이클
  useEffect(() => {
    setDatas((prevDatas) => ({
      ...prevDatas,
      list: initList,
      selectedList: initSelectedList,
    }));
  }, [initList, initSelectedList]);

  // datas값이 변경 될 때 마다 onChange 이벤트 실행
  useEffect(() => {
    const { list, selectedList } = datas;
    onChange({ list: [...list], selectedList: [...selectedList] });

    const newUserListBucket = [];
    const newSelectedUserListBucket = [];
    let curLength = 0;

    if (list?.length > 0) {
      list?.reduce((acc, cur) => {
        if (curLength < cur?.label?.length) {
          curLength = cur?.label?.length;
          return cur;
        }
        return cur;
      });
    }
    list?.forEach((item) => {
      newUserListBucket.push(item);
    });
    selectedList.forEach((item) => {
      newSelectedUserListBucket.push(item);
    });
    setUserList(newUserListBucket);
    setSelectedUserList(newSelectedUserListBucket);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datas]);

  useEffect(() => {
    if (scrollRef.current && datas.list.length > 0) {
      searchInputHandler(inputValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputValue, userList, exceptItem]);

  useEffect(() => {
    if (selectedScrollRef.current && datas.selectedList.length > 0) {
      searchSelectedInputHandler(selectedInputValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUserList]);

  return (
    <div className={cx('multi-select')} ref={innerRef} {...rest}>
      {label && (
        <label className={cx('label')}>
          {t(label)}
          {optional && (
            <span className={cx('optional')}>{t('optional.label')}</span>
          )}
        </label>
      )}
      <div className={cx('list-controller-box')}>
        <div className={cx('list-box', 'available-list')}>
          <p className={cx('title')}>{t(listLabel)}</p>
          <div className={cx('search-box')}>
            <img
              className={cx('search-icon')}
              src='/images/icon/ic-search.svg'
              alt='search-icon'
            />
            <input
              className={cx('search-input')}
              type='text'
              placeholder={t(placeholder ? placeholder : 'inputUser.label')}
              onKeyDown={(e) => onKeyPressHandler(true, e)}
              onChange={(e) => {
                searchInputHandler(e?.target?.value);
              }}
            />
            <div className={cx('search-index')}>
              {filteredArr.length > 0 ? filterIndex.curr : 0}/
              {filteredArr.length}
            </div>
          </div>

          <ul className={cx('list')} ref={scrollRef}>
            {list.map(
              (
                {
                  selected,
                  value,
                  label: labelItem,
                  memberList,
                  deleteDisable,
                },
                idx,
              ) =>
                exceptItem !== value || memberList ? (
                  <Fragment key={`${memberList && 'group-'}${labelItem}`}>
                    {deleteDisable === true ? (
                      <li className={cx('delete-disable')}>
                        <button disabled>{labelItem}</button>
                      </li>
                    ) : (
                      <li
                        className={selected ? cx('selected') : cx('list-item')}
                        ref={(el) => {
                          scrollRef.current && (scrollRef.current[idx] = el);
                        }}
                      >
                        <button
                          onClick={() => {
                            onSelectItem(idx, 'list');
                            setClick(true);
                          }}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              return null;
                            }
                          }}
                        >
                          {memberList && (
                            <Badge
                              customStyle={{
                                marginRight: '4px',
                                fontFamily: 'SqopaM',
                                lineHeight: '12px',
                              }}
                              label='Group'
                              type='green'
                            />
                          )}

                          {userSearchList?.length > 0
                            ? userSearchList[idx]
                            : labelItem}
                        </button>
                      </li>
                    )}
                  </Fragment>
                ) : (
                  <Fragment
                    key={`${memberList && 'group-'}${labelItem}`}
                  ></Fragment>
                ),
            )}
          </ul>
        </div>
        <div className={cx('btns')}>
          <Button
            type='secondary'
            size='small'
            onClick={addAllItem}
            customStyle={{ padding: '0px' }}
            disabled={readOnly}
          >
            <img src='/images/icon/ic-angle-right-all.svg' alt='add all btn' />
          </Button>
          <Button
            type='secondary'
            size='small'
            onClick={addSelectedItem}
            customStyle={{ padding: '0px' }}
            disabled={readOnly}
          >
            <img src='/images/icon/ic-angle-right.svg' alt='add btn' />
          </Button>
          <Button
            type='secondary'
            size='small'
            onClick={removeSelectedItem}
            customStyle={{ padding: '0px' }}
            disabled={readOnly}
          >
            <img src='/images/icon/ic-angle-left.svg' alt='add btn' />
          </Button>
          <Button
            type='secondary'
            size='small'
            onClick={removeAllSelectedItem}
            customStyle={{ padding: '0px' }}
            disabled={readOnly}
          >
            <img src='/images/icon/ic-angle-left-all.svg' alt='add btn' />
          </Button>
        </div>
        <div className={cx('list-box', 'selected-list')}>
          <p className={cx('title')}>{t(selectedLabel)}</p>
          <div className={cx('search-box')}>
            <img
              className={cx('search-icon')}
              src='/images/icon/ic-search.svg'
              alt='search-icon'
            />
            <input
              className={cx('search-input')}
              type='text'
              placeholder={t(placeholder ? placeholder : 'inputUser.label')}
              onKeyDown={(e) => onKeyPressHandler(false, e)}
              onChange={(e) => {
                searchSelectedInputHandler(e?.target?.value);
              }}
            />
            <div className={cx('search-index')}>
              {filterSelectedArr.length > 0 ? filterSelectedIndex.curr : 0}/
              {filterSelectedArr.length}
            </div>
          </div>
          <ul className={cx('list')} ref={selectedScrollRef}>
            {selectedList.map(
              (
                {
                  selected,
                  value,
                  label: labelItem,
                  memberList,
                  deleteDisable,
                },
                idx,
              ) =>
                exceptItem !== value || memberList ? (
                  <Fragment key={idx}>
                    {deleteDisable === true ? (
                      <li className={cx('delete-disable')}>
                        <button disabled>{labelItem}</button>
                      </li>
                    ) : (
                      <li
                        className={selected ? cx('selected') : cx('list-item')}
                        ref={(el) => {
                          selectedScrollRef.current &&
                            (selectedScrollRef.current[idx] = el);
                        }}
                      >
                        <button
                          onClick={() => {
                            onSelectItem(idx, 'selectedList');
                          }}
                        >
                          {memberList && (
                            <Badge
                              customStyle={{
                                marginRight: '4px',
                              }}
                              label='Group'
                              type='green'
                            />
                          )}
                          {selectedUserSearchList?.length > 0
                            ? selectedUserSearchList[idx]
                            : labelItem}
                        </button>
                      </li>
                    )}
                  </Fragment>
                ) : (
                  <Fragment key={idx}></Fragment>
                ),
            )}
          </ul>
        </div>
      </div>
      {error && <span className={cx('error')}>{t(error)}</span>}
    </div>
  );
}

export default MultiSelect;
