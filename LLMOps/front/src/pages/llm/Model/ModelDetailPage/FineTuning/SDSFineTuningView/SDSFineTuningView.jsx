import SDSExternalFineTuningView from './SDSExternalFineTuningView';
import SDSMultimodalFineTuningView from './SDSMultimodalFineTuningView';

const SDSFineTuningView = ({ fineTuningData, ...props }) => {
  if (fineTuningData?.training_type === 'external') {
    return (
      <SDSExternalFineTuningView
        {...props}
        fineTuningData={fineTuningData}
      />
    );
  }

  return (
    <SDSMultimodalFineTuningView
      {...props}
      fineTuningData={fineTuningData}
    />
  );
};

export default SDSFineTuningView;
