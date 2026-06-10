// i18n
import { useTranslation } from 'react-i18next';

// Components
import {
  InputText,
  Button,
  Selectbox,
  Switch,
  Tooltip,
} from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './PortForwardingInputBox.module.scss';
const cx = classNames.bind(style);

function PortForwardingInputBox({
  portForwardingList,
  protocolList,
  targetPortRange,
  nodePortRange,
  warningMessage,
  errorMessage,
  /** 이벤트 핸들러 */
  addInputForm,
  removeInputForm,
  inputHandler, // 입력 이벤트 핸들러
  visualStatus,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('wrapper')}>
      <div className={cx('port-list')}>
        <div className={cx('label-box')}>
          <label className={cx('label')}>
            <span>
              {t('portName.label')}
              <Tooltip contents={t('nameRule.message')} verticalAlign='top' />
            </span>
          </label>
          <label className={cx('label')}>
            <span>{t('protocol.label')}</span>
          </label>
          <label className={cx('label')}>
            <span>
              {t('targetPort.label')}
              <Tooltip
                contents={t('portRule.tooltip.message', {
                  type: 'Target',
                  from: targetPortRange[0],
                  to: targetPortRange[1],
                })}
                contentsAlign={{ vertical: 'top' }}
              />
            </span>
          </label>
          <label className={cx('label')}>
            <span>
              {t('nodePort.label')}
              <Tooltip
                contents={t('portRule.tooltip.message', {
                  type: 'Node',
                  from: nodePortRange[0],
                  to: nodePortRange[1],
                })}
                contentsAlign={{ vertical: 'top' }}
              />
            </span>
            <span className={cx('optional')}>* {t('optional.label')}</span>
          </label>
          <label className={cx('label')}>
            <span>{t('portDescription.label')}</span>
            <span className={cx('optional')}>* {t('optional.label')}</span>
          </label>
          <label className={cx('label')}>
            <span>{t('enable.label')}</span>
          </label>
        </div>
        {portForwardingList?.length > 0 ? (
          portForwardingList?.map(
            (
              {
                name,
                protocol,
                targetPort,
                nodePort,
                description,
                systemDefinition,
                serviceType,
                status,
              },
              idx,
            ) => {
              return (
                <div key={idx} className={cx('input-box')}>
                  <div className={cx('input-wrap')}>
                    <InputText
                      size='medium'
                      name='name'
                      value={name}
                      onChange={(e) => {
                        inputHandler(e, idx);
                      }}
                      disableClearBtn={systemDefinition}
                      onClear={() =>
                        inputHandler(
                          { target: { name: 'name', value: '' } },
                          idx,
                        )
                      }
                      isReadOnly={systemDefinition}
                    />
                  </div>
                  <div className={cx('input-wrap')}>
                    <Selectbox
                      list={protocolList}
                      selectedItem={protocol}
                      onChange={(_, __, e) => {
                        inputHandler(e, idx, 'protocol');
                      }}
                      isReadOnly={visualStatus?.portInfo.disable}
                    />
                  </div>
                  <div className={cx('input-wrap')}>
                    <InputText
                      size='medium'
                      name='targetPort'
                      value={targetPort}
                      onChange={(e) => {
                        inputHandler(e, idx);
                      }}
                      disableClearBtn={visualStatus?.portInfo.disable}
                      onClear={() =>
                        inputHandler(
                          { target: { name: 'targetPort', value: '' } },
                          idx,
                        )
                      }
                      isReadOnly={visualStatus?.portInfo.disable}
                    />
                  </div>
                  <div className={cx('input-wrap')}>
                    <InputText
                      size='medium'
                      name='nodePort'
                      value={nodePort}
                      onChange={(e) => {
                        inputHandler(e, idx);
                      }}
                      disableClearBtn={
                        serviceType === 'ClusterIP' ||
                        visualStatus?.portInfo.disable
                      }
                      onClear={() =>
                        inputHandler(
                          { target: { name: 'nodePort', value: '' } },
                          idx,
                        )
                      }
                      isReadOnly={
                        serviceType === 'ClusterIP' ||
                        visualStatus?.portInfo.disable
                      }
                    />
                  </div>
                  <div className={cx('input-wrap')}>
                    <InputText
                      size='medium'
                      name='description'
                      value={description}
                      onChange={(e) => {
                        inputHandler(e, idx);
                      }}
                      disableClearBtn={
                        systemDefinition || visualStatus?.portInfo.disable
                      }
                      onClear={() =>
                        inputHandler(
                          { target: { name: 'description', value: '' } },
                          idx,
                        )
                      }
                      isReadOnly={
                        systemDefinition || visualStatus?.portInfo.disable
                      }
                    />
                  </div>
                  <div className={cx('input-wrap')}>
                    <Switch
                      checked={status}
                      onChange={(e) => {
                        inputHandler(e, idx, 'status');
                      }}
                      disabled={visualStatus?.portInfo.disable} /* 사용버튼 */
                    />
                  </div>
                  <button
                    className={cx('remove-btn', systemDefinition && 'disabled')}
                    onClick={() => {
                      if (!systemDefinition) {
                        removeInputForm(idx);
                      }
                    }}
                  ></button>
                </div>
              );
            },
          )
        ) : (
          <div></div>
        )}
      </div>
      <div className={cx('btn-wrap')}>
        <Button
          type='secondary'
          onClick={addInputForm}
          disabled={visualStatus?.portInfo.disable} /* 추가버튼 */
        >
          {t('add.label')}
        </Button>
        <div className={cx('message')}>
          <span className={cx('warning')}>{warningMessage}</span>
          <span className={cx('error')}>{errorMessage}</span>
        </div>
      </div>
    </div>
  );
}

export default PortForwardingInputBox;
