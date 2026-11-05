// Atom
import { Modal } from '@jonathan/ui-react';

function DeployWorkerMemoModal({
  data,
  type,
  memo,
  textareaInputHandler,
  t,
  workerId,
}) {
  const { headerRender, contentRender, footerRender, submit, memoEdit } = data;
  const newSubmit = () => {
    submit(memo);
    memoEdit(workerId, memo); // 메모 수정
  };

  const props = {
    headerProps: {
      t,
    },
    contentProps: {
      memo,
      textareaInputHandler,
      t,
    },
    footerProps: {
      submit: newSubmit,
      type,
      t,
    },
  };

  const modalContentsStyle = {
    headerStyle: {
      height: '45px',
      fontSize: '20px',
      fontFamily: 'SpoqaB',
      color: '#121619',
      padding: '32px 44px 0px 44px',
    },
    contentStyle: {
      height: '155px',
      padding: '0px 44px 0px 44px',
    },
    footerStyle: {
      padding: '0px 44px 24px 44px',
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
      topAnimation='calc(50% - 160px)'
    />
  );
}

export default DeployWorkerMemoModal;
