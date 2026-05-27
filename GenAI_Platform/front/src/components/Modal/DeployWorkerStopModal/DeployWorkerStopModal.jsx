// Atoms
import { Modal } from '@jonathan/ui-react';

function DeployWorkerStopModal({ data, type, t }) {
  const { headerRender, contentRender, footerRender, submit } = data;

  const props = {
    headerProps: {
      t,
    },
    contentProps: {
      t,
    },
    footerProps: {
      submit,
      type,
      t,
    },
  };

  const modalContentsStyle = {
    headerStyle: {
      height: '60px',
      fontSize: '20px',
      color: '#666',
      padding: '36px 36px 0px 44px',
    },
    contentStyle: {
      height: '100px',
      padding: '0px 36px 0px 44px',
    },
    footerStyle: {
      padding: '0px 36px 24px 44px',
    },
  };

  return (
    <Modal
      HeaderRender={headerRender}
      ContentRender={contentRender}
      FooterRender={footerRender}
      headerProps={props.headerProps}
      contentProps={props.contentProps}
      footerProps={props.footerProps}
      headerStyle={modalContentsStyle.headerStyle}
      contentStyle={modalContentsStyle.contentStyle}
      footerStyle={modalContentsStyle.footerStyle}
      topAnimation='30%'
    />
  );
}

export default DeployWorkerStopModal;
