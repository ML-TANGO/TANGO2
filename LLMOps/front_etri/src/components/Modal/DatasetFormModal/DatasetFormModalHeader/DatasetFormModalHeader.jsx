function DatasetFormModalHeader({ type, t }) {
  return (
    <>
      {type === 'CREATE_DATASET'
        ? t('createDatasetForm.title.label')
        : t('editDatasetForm.title.label')}
    </>
  );
}

export default DatasetFormModalHeader;
