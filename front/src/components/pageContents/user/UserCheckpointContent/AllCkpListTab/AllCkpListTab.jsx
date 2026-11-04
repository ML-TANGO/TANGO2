import { useState, useCallback, useEffect } from 'react';
import { useRouteMatch } from 'react-router-dom';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button } from '@jonathan/ui-react';
import Table from '@src/components/molecules/Table';
import ListFilter from '@src/components/pageContents/user/UserCheckpointContent/ListFilter';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';

function AllCkpListTab() {
  // Component State
  const [ckpList, setCkpList] = useState([]);

  // Router Hooks
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const { t } = useTranslation();

  const noop = () => {
    alert('준비중');
  };

  const columns = [
    {
      name: t('fileName.label'),
      selector: 'checkpoint_file_name',
      sortable: true,
      minWidth: '200px',
    },
    {
      name: t('trainingName.label'),
      selector: 'training_name',
      maxWidth: '250px',
      sortable: true,
    },
    {
      name: t('type.label'),
      selector: 'checkpoint_type',
      maxWidth: '100px',
      sortable: true,
    },
    {
      name: t('size.label'),
      selector: 'checkpoint_size',
      maxWidth: '100px',
      sortable: true,
    },
    {
      name: t('deployment.label'),
      maxWidth: '80px',
      cell: () => {
        return (
          <Button type='secondary' size='x-small' onClick={noop}>
            Deploy
          </Button>
        );
      },
    },
    {
      name: t('edit.label'),
      maxWidth: '80px',
      cell: () => {
        return (
          <Button type='secondary' size='x-small' onClick={noop}>
            Edit
          </Button>
        );
      },
    },
    {
      name: t('download.label'),
      maxWidth: '100px',
      cell: () => {
        return (
          <Button type='secondary' size='x-small' onClick={noop}>
            Download
          </Button>
        );
      },
    },
  ];

  const getCkpList = useCallback(async () => {
    const response = await callApi({
      url: `checkpoints?workspace_id=${workspaceId}`,
      method: 'get',
    });

    const { status, result, message } = response;

    if (status === STATUS_SUCCESS) {
      setCkpList(result);
    } else if (status === STATUS_FAIL) {
      toast.error(message);
    } else {
      toast.error(message);
    }
  }, [workspaceId]);

  useEffect(() => {
    getCkpList();
  }, [getCkpList]);

  return (
    <div>
      <ListFilter refreshData={getCkpList} />
      <Table
        columns={columns}
        data={ckpList}
        loading={false}
        // selectableRows={false}
      />
    </div>
  );
}

export default AllCkpListTab;
