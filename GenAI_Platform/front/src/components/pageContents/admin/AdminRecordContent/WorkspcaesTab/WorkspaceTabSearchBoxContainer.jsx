import { useState, useCallback, useEffect } from 'react';
import dayjs from 'dayjs';

// i18n
import { useTranslation } from 'react-i18next';

// Containers
import MonthMultiCheckSelectContainer from '@src/containers/MonthMultiCheckSelectContainer';
import WorkspaceMultiCheckSelectContainer from '@src/containers/WorkspaceMultiCheckSelectContainer';

// Components
import SearchBox from '../SearchBox';
import { Selectbox } from '@jonathan/ui-react';

const cYear = dayjs().year();

const WorkspaceTabSearchBoxContainer = ({
  onSearch,
  chipList = [],
  removeChip,
}) => {
  const { t } = useTranslation();
  // STATE
  const [yearOption, setYearOption] = useState({
    year: null,
    yearOptions: new Array(5)
      .fill(null)
      .map((d, i) => ({ label: cYear - i, value: cYear - i })),
  });

  const [monthOption, setMonthOptions] = useState({
    monthOptions: [],
  });

  const [workspaceOption, setWorkspaceOptions] = useState({
    workspaceOptions: [],
  });

  // const [resetInput, setResetInput] = useState(false);

  const onChangeSelectBox = useCallback(
    (value) => {
      setYearOption({
        ...yearOption,
        year: value,
      });
    },
    [setYearOption, yearOption],
  );

  // const onResetInput = () => {
  //   setYearOption({
  //     ...yearOption,
  //     year: null,
  //   });
  //   setMonthOptions({
  //     ...monthOption,
  //     monthOptions: [],
  //   });
  //   setWorkspaceOptions({
  //     ...workspaceOption,
  //     workspaceOptions: [],
  //   });
  //   setResetInput(!resetInput);
  // };

  const catchOnSearch = useCallback(() => {
    const { year } = yearOption;
    const { monthOptions } = monthOption;
    const { workspaceOptions } = workspaceOption;

    // chips
    const yearOpts = year
      ? [
          {
            label: `Year: ${year.value}`,
            origin: year,
            param: { key: 'year', value: year.value },
          },
        ]
      : [];
    const monthOpts = monthOptions
      .filter(({ checked }) => checked)
      .map((opt) => ({
        label: `Month: ${opt.value}`,
        origin: opt,
        param: { key: 'months', value: opt.value },
      }));
    const workspaceOpts = workspaceOptions
      .filter(({ checked }) => checked)
      .map((opt) => ({
        label: `Workspace: ${opt.label}`,
        origin: opt,
        param: { key: 'workspaces', value: opt.value },
      }));
    const newChipList = [...yearOpts, ...monthOpts, ...workspaceOpts];
    onSearch(newChipList);
    // onResetInput();
  }, [onSearch, yearOption, monthOption, workspaceOption]);

  const multiCheckSubmit = useCallback(
    (target, data) => {
      if (target === 'monthOption') {
        setMonthOptions({
          ...monthOption,
          monthOptions: data,
        });
      } else if (target === 'workspaceOption') {
        setWorkspaceOptions({
          ...workspaceOption,
          workspaceOptions: data,
        });
      }
    },
    [monthOption, setMonthOptions, workspaceOption, setWorkspaceOptions],
  );

  const syncWorkspaceOptions = useCallback((syncArray) => {
    setWorkspaceOptions((wOpt) => {
      const { workspaceOptions: wOpts } = wOpt;
      const newOptions = wOpts.map((v) => {
        let checked = false;
        for (let i = 0; i < syncArray.length; i += 1) {
          if (syncArray[i] === v.value) {
            checked = true;
            break;
          }
        }
        return { ...v, checked };
      });
      return { ...wOpt, workspaceOptions: newOptions };
    });
  }, []);

  const syncYearOptions = useCallback((syncValue) => {
    setYearOption((yOpt) => ({
      ...yOpt,
      year: syncValue,
    }));
  }, []);

  const syncMonthOptions = useCallback(
    (syncArray) => {
      setMonthOptions((mOpt) => {
        const { monthOptions: mOpts } = mOpt;
        const newOptions = mOpts.map((v) => {
          let checked = false;
          for (let i = 0; i < syncArray.length; i += 1) {
            if (syncArray[i] === v.value) {
              checked = true;
              break;
            }
          }
          return { ...v, checked };
        });
        return { ...mOpt, monthOptions: newOptions };
      });
    },
    [setMonthOptions],
  );

  useEffect(() => {
    const workspaceSyncArray = [];
    let yearSyncValue = null;
    const monthSyncArray = [];
    for (let i = 0; i < chipList.length; i += 1) {
      const {
        param: { key },
        origin,
      } = chipList[i];
      if (key === 'workspaces') {
        const { value: workspaceId } = origin;
        workspaceSyncArray.push(workspaceId);
      } else if (key === 'year') {
        const { value: yearValue } = origin;
        yearSyncValue = yearValue;
      } else if (key === 'months') {
        const { value: monthValue } = origin;
        monthSyncArray.push(monthValue);
      }
    }
    syncWorkspaceOptions(workspaceSyncArray);
    syncYearOptions(
      yearSyncValue
        ? { label: yearSyncValue, value: yearSyncValue }
        : yearSyncValue,
    );
    if (yearSyncValue && monthSyncArray.length !== 0)
      syncMonthOptions(monthSyncArray);
    else syncMonthOptions([]);
  }, [chipList, syncMonthOptions, syncWorkspaceOptions, syncYearOptions]);

  const { yearOptions, year } = yearOption;
  const { monthOptions } = monthOption;
  const { workspaceOptions } = workspaceOption;
  return (
    <SearchBox
      onSearch={catchOnSearch}
      selectedList={chipList}
      removeChip={removeChip}
    >
      <Selectbox
        size='medium'
        list={yearOptions}
        selectedItem={year}
        placeholder={t('selectYear.placeholder')}
        onChange={(value) => {
          onChangeSelectBox(value);
        }}
        customStyle={{ globalForm: { width: '160px' } }}
      />
      <MonthMultiCheckSelectContainer
        submit={multiCheckSubmit}
        selectedOptions={monthOptions}
        // reset={resetInput}
        readOnly={!year}
      />
      <WorkspaceMultiCheckSelectContainer
        submit={multiCheckSubmit}
        selectedOptions={workspaceOptions}
        // reset={resetInput}
      />
    </SearchBox>
  );
};

export default WorkspaceTabSearchBoxContainer;
