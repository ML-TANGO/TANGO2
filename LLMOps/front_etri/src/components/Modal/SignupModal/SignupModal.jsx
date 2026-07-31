// Components
import SignupModalContent from '@src/components/modalContents/SignupModalContents/SignupModalContent';

function SignupModal({ type, data: modalData }) {
  return <SignupModalContent type={type} modalData={modalData} />;
}

export default SignupModal;
