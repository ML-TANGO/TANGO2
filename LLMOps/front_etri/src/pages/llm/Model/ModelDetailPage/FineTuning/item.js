export const rangeBarTitle = [
  {
    label: 'Number of Epochs',
    valueTitle: 'numberOfEpochs',
    min: 1,
    max: 100,
    step: 1,
  },
  {
    label: 'Gradient Accumulation Steps',
    valueTitle: 'gradientAccumulationSteps',
    min: 1,
    max: 32,
    step: 1,
  },
  {
    label: 'Cutoff Length',
    valueTitle: 'cutoffLength',
    min: 64,
    max: 4096,
    step: 64,
  },
  {
    label: 'Learning Rate',
    valueTitle: 'learningRate',
    min: 0.000001,
    max: 0.01,
    step: 0.000001,
  },
  {
    label: 'Warmup Steps',
    valueTitle: 'warmupSteps',
    min: 0,
    max: 10000,
    step: 100,
  },
];

export const fineTuningTypeOptions = [
  {
    label: '일반',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: '고급',
    value: 2,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

export const initialValue = {
  numberOfEpochs: 0,
  gradientAccumulationSteps: 0,
  cutoffLength: 0,
  learningRate: 0,
  warmupSteps: 0,
};
