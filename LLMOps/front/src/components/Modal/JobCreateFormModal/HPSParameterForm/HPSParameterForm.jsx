// Components
import { Button, InputText } from '@jonathan/ui-react';

import { useState } from 'react';

import Number from '@src/components/atoms/input/Number';
import Radio from '@src/components/atoms/input/Radio';
import CheckboxList from '@src/components/molecules/CheckboxList';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
// CSS Module
import style from './HPSParameterForm.module.scss';

const cx = classNames.bind(style);

const HPSParameterForm = ({
  modalType,
  loadFile,
  trainingType,
  hpsParameter,
  initPoint,
  searchCount,
  interval,
  paramInputHandler,
  hyperParamRadioBtnHandler,
  addHyperParameter,
  removeHyperParameter,
  hyperParameterInputTextHandler,
  hyperParameterDataTypeHandler,
  error,
  t,
}) => {
  const [dupMessage, setDupMessage] = useState(false);
  const textInputDupCheckHandler = () => {
    let inputBucket = [];
    hpsParameter.map((el) => inputBucket.push(el.paramList[0].value));

    const setData = new Set(inputBucket);
    if (inputBucket.length !== setData.size) {
      setDupMessage(true);
    } else {
      setDupMessage(false);
    }
  };

  return (
    <>
      <div className={cx('hyper-parameter-form')}>
        <div className={cx('parameter-list')}>
          {hpsParameter.map(
            (
              { paramList, paramTypeOptions, paramType, isStatic, isInt },
              i,
            ) => {
              return (
                <div className={cx('parameter')} key={i}>
                  <div className={cx('parameter-top')}>
                    {paramList[0] &&
                      (paramList[0].isBuiltIn ? (
                        <span className={cx('default-value')}>
                          {paramList[0].value}
                        </span>
                      ) : (
                        <InputText
                          size='medium'
                          placeholder={t(`${paramList[0].label}`)}
                          value={paramList[0].value}
                          onChange={(e) => {
                            hyperParameterInputTextHandler(
                              i,
                              0,
                              e.target.value,
                              isInt,
                            );
                            textInputDupCheckHandler();
                          }}
                          disableLeftIcon={true}
                          disableClearBtn={false}
                          onClear={() => {
                            hyperParameterInputTextHandler(i, 0, '', isInt);
                            textInputDupCheckHandler();
                          }}
                          isReadOnly={isStatic}
                        />
                      ))}
                    <Radio
                      options={paramTypeOptions}
                      value={paramType}
                      onChange={(v) => {
                        hyperParamRadioBtnHandler(i, v);
                      }}
                      readOnly={isStatic}
                    />
                    {paramType === 1 ? (
                      <div className={cx('datatype-check-box')}>
                        <CheckboxList
                          options={[{ label: 'Int', checked: isInt }]}
                          onChange={() => {
                            hyperParameterDataTypeHandler(i, isInt);
                          }}
                          disableErrorText
                        />
                      </div>
                    ) : (
                      <span className={cx('datatype-check-box')}></span>
                    )}
                  </div>
                  <div className={cx('float-box')}>
                    {paramList.map(({ label, value }, j) => {
                      if (j === 0) return null;
                      if (paramType === 0 && j > 1) {
                        return null;
                      }
                      if (paramType === 1 && j === 1) {
                        return null;
                      }
                      if (label === 'value.label') {
                        return (
                          <div className={cx('param-input')} key={j}>
                            <InputBoxWithLabel
                              labelText={t(label)}
                              labelSize='small'
                              disableErrorMsg
                            >
                              <InputText
                                size='medium'
                                placeholder={t('value.label')}
                                value={value}
                                onChange={(e) => {
                                  hyperParameterInputTextHandler(
                                    i,
                                    j,
                                    e.target.value,
                                    isInt,
                                  );
                                }}
                                onClear={() =>
                                  hyperParameterInputTextHandler(
                                    i,
                                    j,
                                    '',
                                    isInt,
                                  )
                                }
                                disableLeftIcon
                                disableClearBtn={isStatic}
                                isReadOnly={isStatic}
                              />
                            </InputBoxWithLabel>
                          </div>
                        );
                      }
                      if (label === 'count.label') {
                        return (
                          <div className={cx('param-input')} key={j}>
                            <label className={cx('label')}>{t(label)}</label>
                            <Number
                              size='medium'
                              placeholder={t(label)}
                              name='searchCount'
                              value={searchCount}
                              onChange={(e) => {
                                paramInputHandler(e, i);
                              }}
                              min={1}
                              disabledErrorText
                            />
                          </div>
                        );
                      }
                      if (label === 'initPoints.label') {
                        return (
                          <div className={cx('param-input')} key={j}>
                            <label className={cx('label')}>{t(label)}</label>
                            <Number
                              size='medium'
                              placeholder={t(label)}
                              name='initPoint'
                              value={initPoint}
                              onChange={(e) => {
                                paramInputHandler(e, i);
                              }}
                              min={1}
                              disabledErrorText
                            />
                          </div>
                        );
                      }
                      if (label === 'interval.label') {
                        return (
                          <div className={cx('param-input')} key={j}>
                            <label className={cx('label')}>{t(label)}</label>
                            <Number
                              size='medium'
                              placeholder={t(label)}
                              name='interval'
                              value={interval}
                              onChange={(e) => {
                                paramInputHandler(e, i);
                              }}
                              min={0}
                              disabledErrorText
                            />
                          </div>
                        );
                      }
                      return (
                        <div className={cx('param-input')} key={j}>
                          <label className={cx('label')}>{t(label)}</label>
                          <InputText
                            size='medium'
                            placeholder={t(label)}
                            value={value}
                            onChange={(e) => {
                              const { value: v } = e.target;
                              hyperParameterInputTextHandler(i, j, v, isInt);
                            }}
                            isReadOnly={isStatic && label === 'value.label'}
                          />
                        </div>
                      );
                    })}
                    {/* {!(trainingType === 'built-in') && (
                      <button
                        className={cx(
                          'remove-btn',
                          (hpsParameter.length === 1 || isStatic) && 'disabled',
                        )}
                        onClick={() => {
                          if (hpsParameter.length !== 1 && !isStatic) {
                            removeHyperParameter(i);
                          }
                        }}
                      ></button>
                    )} */}
                  </div>
                </div>
              );
            },
          )}
        </div>
        <div className={cx('btn-wrap')}>
          {modalType !== 'ADD_HPS' && !(trainingType === 'built-in') && (
            <Button
              type='secondary'
              size='medium'
              onClick={addHyperParameter}
              customStyle={{ marginTop: '20px' }}
            >
              {t('add.label')}
            </Button>
          )}
        </div>
      </div>
      <span className={cx('error')}>
        {dupMessage ? t('hyperParameterInput.duplicate.message') : t(error)}
      </span>
    </>
  );
};

export default HPSParameterForm;
