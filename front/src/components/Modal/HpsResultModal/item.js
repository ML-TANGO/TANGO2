export const test = {
  result: {
    hps_name: 'teqgeqgeq',
    parameter: {
      parameter: [
        {
          name: 'batch_size',
          type: 'int',
          min: 1,
          max: 5,
          step: 12,
        },
        {
          name: 'learning_rate',
          type: 'float',
          min: 0.00005,
          max: 0.0001,
          step: 12,
        },
      ],
      fixed_parameter: [
        {
          name: 'epochs',
          value: 5,
        },
      ],
    },
    best_params: {
      batch_size: 2,
      learning_rate: 0.000099519666588003,
    },
    best_value: {
      target_metric: 'loss',
      value: 2.678144,
    },
    result: [
      {
        id: '1',
        params: {
          batch_size: 2,
          learning_rate: 0.000089905352241344,
          epochs: 5,
          loss: 1.804361,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.804361, 1.711086, 1.634702, 1.541212, 1.824512],
            },
            {
              key: 'learning_rate',
              values: [
                0.000089905352241344, 0.000089905352241344,
                0.000089905352241344, 0.000089905352241344,
                0.000089905352241344,
              ],
            },
            {
              key: 'batch_size',
              values: [2, 2, 2, 2, 2],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.804361, "learning_rate": 8.990535224134456e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.711086, "learning_rate": 8.990535224134456e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.634702, "learning_rate": 8.990535224134456e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.541212, "learning_rate": 8.990535224134456e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 1.824512, "learning_rate": 8.990535224134456e-05, "batch_size": 2}\n',
        ],
      },
      {
        id: '2',
        params: {
          batch_size: 4,
          learning_rate: 0.000097977284796158,
          epochs: 5,
          loss: 0.916546,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [0.916546, 0.81188, 0.732426, 0.909894, 0.721641],
            },
            {
              key: 'learning_rate',
              values: [
                0.000097977284796158, 0.000097977284796158,
                0.000097977284796158, 0.000097977284796158,
                0.000097977284796158,
              ],
            },
            {
              key: 'batch_size',
              values: [4, 4, 4, 4, 4],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 0.916546, "learning_rate": 9.79772847961584e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 0.81188, "learning_rate": 9.79772847961584e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 0.732426, "learning_rate": 9.79772847961584e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 0.909894, "learning_rate": 9.79772847961584e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 0.721641, "learning_rate": 9.79772847961584e-05, "batch_size": 4}\n',
        ],
      },
      {
        id: '3',
        params: {
          batch_size: 3,
          learning_rate: 0.000068961100064691,
          epochs: 5,
          loss: 1.432286,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.432286, 1.388787, 1.331657, 1.269876, 1.099319],
            },
            {
              key: 'learning_rate',
              values: [
                0.000068961100064691, 0.000068961100064691,
                0.000068961100064691, 0.000068961100064691,
                0.000068961100064691,
              ],
            },
            {
              key: 'batch_size',
              values: [3, 3, 3, 3, 3],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.432286, "learning_rate": 6.896110006469182e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.388787, "learning_rate": 6.896110006469182e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.331657, "learning_rate": 6.896110006469182e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.269876, "learning_rate": 6.896110006469182e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 1.099319, "learning_rate": 6.896110006469182e-05, "batch_size": 3}\n',
        ],
      },
      {
        id: '4',
        params: {
          batch_size: 4,
          learning_rate: 0.000080785433677103,
          epochs: 5,
          loss: 1.058101,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.058101, 1.022851, 1.022599, 0.885652, 0.703232],
            },
            {
              key: 'learning_rate',
              values: [
                0.000080785433677103, 0.000080785433677103,
                0.000080785433677103, 0.000080785433677103,
                0.000080785433677103,
              ],
            },
            {
              key: 'batch_size',
              values: [4, 4, 4, 4, 4],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.058101, "learning_rate": 8.078543367710319e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.022851, "learning_rate": 8.078543367710319e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.022599, "learning_rate": 8.078543367710319e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 0.885652, "learning_rate": 8.078543367710319e-05, "batch_size": 4}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 0.703232, "learning_rate": 8.078543367710319e-05, "batch_size": 4}\n',
        ],
      },
      {
        id: '5',
        params: {
          batch_size: 2,
          learning_rate: 0.000078384438091129,
          epochs: 5,
          loss: 1.971811,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.971811, 1.939705, 1.835035, 1.697742, 1.886378],
            },
            {
              key: 'learning_rate',
              values: [
                0.000078384438091129, 0.000078384438091129,
                0.000078384438091129, 0.000078384438091129,
                0.000078384438091129,
              ],
            },
            {
              key: 'batch_size',
              values: [2, 2, 2, 2, 2],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.971811, "learning_rate": 7.838443809112935e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.939705, "learning_rate": 7.838443809112935e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.835035, "learning_rate": 7.838443809112935e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.697742, "learning_rate": 7.838443809112935e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 1.886378, "learning_rate": 7.838443809112935e-05, "batch_size": 2}\n',
        ],
      },
      {
        id: '6',
        params: {
          batch_size: 2,
          learning_rate: 0.000098558628855529,
          epochs: 5,
          loss: 1.256691,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.256691, 1.114558, 1.061437, 1.112919, 1.218367],
            },
            {
              key: 'learning_rate',
              values: [
                0.000098558628855529, 0.000098558628855529,
                0.000098558628855529, 0.000098558628855529,
                0.000098558628855529,
              ],
            },
            {
              key: 'batch_size',
              values: [2, 2, 2, 2, 2],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.256691, "learning_rate": 9.855862885552908e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.114558, "learning_rate": 9.855862885552908e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.061437, "learning_rate": 9.855862885552908e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.112919, "learning_rate": 9.855862885552908e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 1.218367, "learning_rate": 9.855862885552908e-05, "batch_size": 2}\n',
        ],
      },
      {
        id: '7',
        params: {
          batch_size: 2,
          learning_rate: 0.000099519666588003,
          epochs: 5,
          loss: 2.678144,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [2.678144, 2.630654, 2.665991, 2.491008, 2.553945],
            },
            {
              key: 'learning_rate',
              values: [
                0.000099519666588003, 0.000099519666588003,
                0.000099519666588003, 0.000099519666588003,
                0.000099519666588003,
              ],
            },
            {
              key: 'batch_size',
              values: [2, 2, 2, 2, 2],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 2.678144, "learning_rate": 9.951966658800393e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 2.630654, "learning_rate": 9.951966658800393e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 2.665991, "learning_rate": 9.951966658800393e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 2.491008, "learning_rate": 9.951966658800393e-05, "batch_size": 2}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 2.553945, "learning_rate": 9.951966658800393e-05, "batch_size": 2}\n',
        ],
      },
      {
        id: '8',
        params: {
          batch_size: 3,
          learning_rate: 0.000063439272655432,
          epochs: 5,
          loss: 2.124392,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [2.124392, 2.139616, 1.99672, 1.808968, 2.017071],
            },
            {
              key: 'learning_rate',
              values: [
                0.000063439272655432, 0.000063439272655432,
                0.000063439272655432, 0.000063439272655432,
                0.000063439272655432,
              ],
            },
            {
              key: 'batch_size',
              values: [3, 3, 3, 3, 3],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 2.124392, "learning_rate": 6.343927265543215e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 2.139616, "learning_rate": 6.343927265543215e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.99672, "learning_rate": 6.343927265543215e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.808968, "learning_rate": 6.343927265543215e-05, "batch_size": 3}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 2.017071, "learning_rate": 6.343927265543215e-05, "batch_size": 3}\n',
        ],
      },
      {
        id: '9',
        params: {
          batch_size: 5,
          learning_rate: 0.000080901607189959,
          epochs: 5,
          loss: 2.472764,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [2.472764, 2.451997, 2.250181, 2.160133, 2.329712],
            },
            {
              key: 'learning_rate',
              values: [
                0.000080901607189959, 0.000080901607189959,
                0.000080901607189959, 0.000080901607189959,
                0.000080901607189959,
              ],
            },
            {
              key: 'batch_size',
              values: [5, 5, 5, 5, 5],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 2.472764, "learning_rate": 8.090160718995987e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 2.451997, "learning_rate": 8.090160718995987e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 2.250181, "learning_rate": 8.090160718995987e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 2.160133, "learning_rate": 8.090160718995987e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 2.329712, "learning_rate": 8.090160718995987e-05, "batch_size": 5}\n',
        ],
      },
      {
        id: '10',
        params: {
          batch_size: 5,
          learning_rate: 0.000056377411931211,
          epochs: 5,
          loss: 1.40201,
        },
        train_logs: {
          y: {
            key: 'epoch',
            values: [1, 2, 3, 4, 5],
          },
          x: [
            {
              key: 'iteration_key',
              values: ['epoch', 'epoch', 'epoch', 'epoch', 'epoch'],
            },
            {
              key: 'loss',
              values: [1.40201, 1.289376, 1.271226, 1.323463, 1.026252],
            },
            {
              key: 'learning_rate',
              values: [
                0.000056377411931211, 0.000056377411931211,
                0.000056377411931211, 0.000056377411931211,
                0.000056377411931211,
              ],
            },
            {
              key: 'batch_size',
              values: [5, 5, 5, 5, 5],
            },
          ],
        },
        source_logs: [
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 1, "loss": 1.40201, "learning_rate": 5.6377411931211065e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 2, "loss": 1.289376, "learning_rate": 5.6377411931211065e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 3, "loss": 1.271226, "learning_rate": 5.6377411931211065e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 4, "loss": 1.323463, "learning_rate": 5.6377411931211065e-05, "batch_size": 5}\n',
          '[FLIGHTBASE] {"iteration_key": "epoch", "epoch": 5, "loss": 1.026252, "learning_rate": 5.6377411931211065e-05, "batch_size": 5}\n',
        ],
      },
    ],
  },
  status: 1,
  message: null,
};
