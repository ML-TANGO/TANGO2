// i18n
import { useTranslation } from 'react-i18next';

// Components
import Table from '@src/components/molecules/Table';
import ListFilter from '../ListFilter';

function RegisteredCkpListTab() {
  const { t } = useTranslation();
  const columns = [
    {
      name: t('fileName.label'),
      selector: 'checkpoint_file_name',
      sortable: true,
      maxWidth: '200px',
    },
    {
      name: t('memo.label'),
      selector: 'checkpoint_description',
    },
    {
      name: t('trainingName.label'),
      selector: 'training_name',
      sortable: true,
    },
    {
      name: t('size.label'),
      selector: 'checkpoint_size',
      sortable: true,
    },
    {
      name: t('deployment.label'),
      cell: () => {
        return <button>Deploy</button>;
      },
    },
    {
      name: t('edit.label'),
      cell: () => {
        return <button>Edit</button>;
      },
    },
    {
      name: t('download.label'),
      cell: () => {
        return <button>Download</button>;
      },
    },
  ];

  return (
    <div>
      <ListFilter />
      <Table columns={columns} data={[]} loading={false} />
    </div>
  );
}

export default RegisteredCkpListTab;
