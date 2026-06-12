import { useTranslation } from 'react-i18next';

const SelectedPage = () => {
  const { t } = useTranslation();

  return (
    <div
      style={{
        width: '100%',
        height: 'calc(100vh - 133px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <p
        style={{
          margin: 'initial',
          color: '#121619',
          fontFamily: 'SpoqaM',
          fontSize: '14px',
        }}
      >
        {t('selected.platform.label')}
      </p>
    </div>
  );
};

export default SelectedPage;
