import { ButtonV2 } from '@tango/ui-react';

import RefreshIcon from '@src/static/images/icon/ic-refresh-blue.svg';
import loadingIcon from '@src/static/images/icon/spinner-1s-58.svg';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const RefreshButton = ({ onClick, ...rest }) => {
  const { t } = useTranslation();

  const [isLoading, setIsLoading] = useState(false);
  const handleClick = async () => {
    setIsLoading(true);
    if (onClick) {
      await onClick();
    }
    setIsLoading(false);
  };

  return (
    <ButtonV2
      label={t('refresh.label')}
      size='l'
      colorType='skyblue'
      // iconPosition='left'
      // icon={isLoading ? loadingIcon : RefreshIcon}
      onClick={handleClick}
      {...rest}
    />
  );
};

export default RefreshButton;
