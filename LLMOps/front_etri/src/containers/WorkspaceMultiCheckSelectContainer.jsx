import { useCallback, useEffect, useState } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

// Components
import MultiCheckSelect from '@src/components/molecules/MutliCheckSelect';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

const WorkspaceMultiCheckSelectContainer = ({
  submit,
  selectedOptions,
  reset,
  t,
}) => {
  const [workspaceOptions, setWorkspaceOptions] = useState([]);
  const [workspaceList, setWorkspaceList] = useState([]);
  const [selected, setSelected] = useState(null);

  // workspace 옵션 목록 조회
  const getWorkpsaceOptions = useCallback(async () => {
    const response = await callApi({
      url: 'records/options/workspaces',
      method: 'get',
    });
    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      const { workspace_list: wOptions } = result;
      setWorkspaceList(wOptions);
      if (wOptions.length > 0) {
        setWorkspaceOptions([
          { label: t('all.label'), value: 'all', checked: false },
          ...wOptions.map(({ id, name }) => ({
            label: `${name}`,
            value: id,
            checked: false,
          })),
        ]);
      }
    } else {
      toast.error(message);
    }
  }, [t]);

  const onSubmit = useCallback(
    (opt) => {
      const newOpt = opt.filter(({ checked }) => checked);
      setWorkspaceOptions(opt);
      submit('workspaceOption', newOpt);
      setSelected({ label: `${t('workspace.label')} (${newOpt.length - 1})` });
    },
    [setWorkspaceOptions, submit, t],
  );

  const updateWorkspaceOptions = (newOptions) => {
    setWorkspaceOptions(newOptions);
  };

  useEffect(() => {
    getWorkpsaceOptions();
  }, [getWorkpsaceOptions]);

  useEffect(() => {
    const wList = workspaceList.map(({ id, name }) => ({
      label: name,
      value: id,
      checked: false,
    }));
    let isAll = true;
    let checkCount = 0;
    const newWorkspaceOptions = wList.map((opt) => {
      let checked = false;
      for (let i = 0; i < selectedOptions.length; i += 1) {
        const { value: selectedVal, checked: selectedChecked } =
          selectedOptions[i];
        if (selectedVal === opt.value && selectedChecked) {
          checked = true;
          checkCount += 1;
          break;
        }
      }
      const newOpt = { ...opt, checked };
      if (!checked) isAll = false;
      return newOpt;
    });
    if (newWorkspaceOptions.length > 0)
      updateWorkspaceOptions([
        { label: t('all.label'), value: 'all', checked: isAll },
        ...newWorkspaceOptions,
      ]);
    setSelected(
      checkCount !== 0
        ? { label: `${t('workspace.label')} (${checkCount})` }
        : null,
    );
  }, [selectedOptions, workspaceList, t]);

  useEffect(() => {
    setSelected(null);
  }, [reset]);

  return (
    <MultiCheckSelect
      name={'workspace'}
      options={workspaceOptions}
      placeholder='selectWorkspace.placeholder'
      sizeType={'small'}
      selected={selected}
      onSubmit={onSubmit}
      disabledErrorText
    />
  );
};

export default withTranslation()(WorkspaceMultiCheckSelectContainer);
