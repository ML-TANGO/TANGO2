import { useEffect, useState } from 'react';

// Icons
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import builtInImage from '@src/static/images/icon/ic-built-in-blue.svg';

// Components
import { InputText, Badge, Selectbox } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './BuiltInType.module.scss';

const cx = classNames.bind(style);

function BuiltInType({
  modelList = [],
  modelCategorySelect,
  categoryHandler,
  searchModelHandler,
  selectedModel,
  onClickModelList,
  modelSelectStatusHanlder,
  modelSelectStatus,
  editStatus,
  readOnly,
  t,
}) {
  const [childRef, setChildRef] = useState(null);
  const [parentRef, setParentRef] = useState(null);
  const [categoryList, setCategoryList] = useState([]);

  useEffect(() => {
    if (!modelList || !modelList.built_in_model_list || categoryList.length > 0)
      return;
    const kindList = modelList.built_in_model_list?.map((v) =>
      v.built_in_model_kind.trim(),
    );
    const set = new Set(kindList);
    const uniqueKind = [...set].map((v) => ({ label: v, value: v }));
    setCategoryList([
      { label: t('deployment.model.category.label'), value: 'all' },
      ...uniqueKind,
    ]);
  }, [modelList, t]);

  useEffect(() => {
    if (childRef && parentRef) {
      let top =
        childRef.getBoundingClientRect().top -
        parentRef.getBoundingClientRect().top;
      parentRef.scrollTo({
        top: top - 150,
        behavior: 'smooth',
      });
    }
  }, [childRef, parentRef]);

  return (
    <div className={cx('training-box')}>
      <div
        className={cx(
          'tab',
          !modelSelectStatus && 'close',
          readOnly ? 'readOnly' : 'editable',
        )}
        onClick={() => modelSelectStatusHanlder()}
      >
        <div className={cx('title')}>{t('Model')}</div>
        <div
          className={cx(
            'content',
            selectedModel && 'selected-content',
            readOnly ? 'readOnly' : 'editable',
          )}
        >
          {selectedModel
            ? selectedModel.built_in_model_name
            : t('deployment.model.select.label')}
        </div>
        <div className={cx('arrow-train')}>
          <img
            src={modelSelectStatus && !editStatus ? arrowUp : arrowDown}
            alt='arrow'
          />
        </div>
      </div>
      {modelSelectStatus && !editStatus && (
        <>
          <div className={cx('train-content')}>
            <div className={cx('input')}>
              <InputText
                onChange={(e) => searchModelHandler(e)}
                disableLeftIcon={false}
                options={{ maxLength: 20 }}
                placeholder={t('deployment.model.search.label')}
              />
            </div>
            <div className={cx('select')}>
              <Selectbox
                list={categoryList}
                selectedItem={modelCategorySelect}
                onChange={(value) => {
                  categoryHandler(value);
                }}
                placeholder={t('deployment.model.category.label')}
                customStyle={{
                  fontStyle: {
                    selectbox: {
                      fontSize: '13px',
                    },
                    list: {
                      fontSize: '13px',
                    },
                  },
                }}
              />
            </div>
          </div>
          <div ref={setParentRef} className={cx('train-list')}>
            {modelList?.built_in_model_list?.map((list, idx) => {
              return (
                <div
                  className={cx(
                    list.enable_to_deploy_with_cpu ||
                      list.enable_to_deploy_with_gpu ||
                      list.deployment_multi_gpu_mode
                      ? 'test-box'
                      : 'list-box',
                    selectedModel?.built_in_model_id ===
                      list.built_in_model_id && 'selected-model-list',
                    list.deployment_status === 1 ? 'able' : 'disable',
                  )}
                  ref={
                    selectedModel?.built_in_model_id === list.built_in_model_id
                      ? setChildRef
                      : null
                  }
                  key={idx}
                  onClick={() => {
                    list.deployment_status === 1 && onClickModelList(list);
                  }}
                >
                  <div className={cx('image')}>
                    <img
                      className={cx(
                        list.is_thumbnail === 1 ? 'thumbnail' : 'default',
                      )}
                      src={
                        list.is_thumbnail === 0
                          ? builtInImage
                          : list.built_in_model_thumbnail_image_info[
                              list.built_in_model_id
                            ]
                      }
                      alt='type'
                    />
                  </div>
                  <div className={cx('name-box')}>
                    <div className={cx('name-desc')}>
                      <span className={cx('name')}>
                        {list.built_in_model_name}
                      </span>
                      <span className={cx('desc')}>
                        {list.built_in_model_description}
                      </span>
                    </div>
                  </div>
                  {/* {list.enable_to_deploy_with_cpu ||
                  list.enable_to_deploy_with_gpu ||
                  list.deployment_multi_gpu_mode ? (
                    <div className={cx('badge')}>
                      <Badge
                        type={
                          list.enable_to_deploy_with_cpu ? 'yellow' : 'disabled'
                        }
                        title={
                          list.enable_to_deploy_with_cpu ? 'Multi GPU' : ''
                        }
                        label='CPU'
                        customStyle={{
                          marginLeft: '4px',
                          opacity: list.enable_to_deploy_with_cpu ? '1' : '0.2',
                        }}
                      />
                      <Badge
                        type={
                          list.enable_to_deploy_with_gpu ? 'green' : 'disabled'
                        }
                        title={
                          list.enable_to_deploy_with_gpu ? 'Multi GPU' : ''
                        }
                        label='GPU'
                        customStyle={{
                          marginLeft: '4px',
                          opacity: list.enable_to_deploy_with_gpu ? '1' : '0.2',
                        }}
                      />
                      <Badge
                        type={list.isDeploymentMultiGpu ? 'blue' : 'disabled'}
                        title={
                          list.deployment_multi_gpu_mode ? 'Multi GPU' : ''
                        }
                        label='Multi'
                        customStyle={{
                          marginLeft: '4px',
                          opacity: list.deployment_multi_gpu_mode ? '1' : '0.2',
                        }}
                      />
                    </div>
                  ) : (
                    <></>
                  )} */}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

export default BuiltInType;
