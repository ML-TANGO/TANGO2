import { __assign } from '../../../../../_virtual/_tslib.js';
import { jsxs, jsx } from 'react/jsx-runtime';
import { useRef, useCallback, useEffect } from 'react';
import { theme } from '../../../../utils/utils.js';
import classNames from '../../../../../modules/classnames/bind.js';
import style from './Tab.module.scss.js';

var cx = classNames.bind(style);
function Tab(_a) {
    var category = _a.category, selectedItem = _a.selectedItem, renderComponent = _a.renderComponent, renderComponentProps = _a.renderComponentProps, customStyle = _a.customStyle, theme = _a.theme, _b = _a.isScroll, isScroll = _b === void 0 ? true : _b, _c = _a.isScrollCorrection, isScrollCorrection = _c === void 0 ? true : _c, onClick = _a.onClick, t = _a.t;
    var componentRef = useRef(null);
    var handleScroll = useCallback(function (e) {
        if (componentRef.current &&
            !componentRef.current.contains(e.target)) {
            var component = componentRef.current;
            var _a = document.documentElement, scrollHeight = _a.scrollHeight, scrollTop = _a.scrollTop, clientHeight = _a.clientHeight;
            if (scrollTop === 0) {
                component.scrollTo({
                    top: component.scrollTop - 500,
                    behavior: 'smooth',
                });
            }
            else if (scrollTop + clientHeight >= scrollHeight) {
                component.scrollTo({
                    top: component.scrollTop + 500,
                    behavior: 'smooth',
                });
            }
        }
    }, []);
    useEffect(function () {
        if (isScrollCorrection) {
            window.addEventListener('wheel', handleScroll);
            return function () {
                window.removeEventListener('wheel', handleScroll);
            };
        }
        return function () { };
    }, [handleScroll, isScrollCorrection]);
    return (jsxs("div", __assign({ className: cx('tab'), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.tab }, { children: [jsxs("div", __assign({ className: cx('tab-controller', theme) }, { children: [jsx("ul", __assign({ className: cx('btn-area', theme), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.selectBtnArea }, { children: category === null || category === void 0 ? void 0 : category.map(function (data, idx) {
                            return (jsx("li", __assign({ className: cx(idx === selectedItem && 'selected-tab', theme), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.label, onClick: function (e) {
                                    if (onClick) {
                                        var compo = componentRef.current;
                                        if (compo) {
                                            compo.scrollTo({
                                                top: 0,
                                                behavior: 'smooth',
                                            });
                                        }
                                        onClick(idx, e);
                                    }
                                } }, { children: t ? t(data.label) : data.label }), idx));
                        }) })), jsx("div", { className: cx('line', theme), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.line })] })), jsx("div", __assign({ className: cx('child', isScroll && 'scroll', theme), style: customStyle === null || customStyle === void 0 ? void 0 : customStyle.component, ref: componentRef }, { children: renderComponent && renderComponent(renderComponentProps) }))] })));
}
Tab.defaultProps = {
    category: [],
    selectedItem: undefined,
    renderComponent: undefined,
    renderComponentProps: undefined,
    customStyle: {
        tabArea: {},
        selectBtnArea: {},
        label: {},
        line: {},
        component: {},
    },
    isScroll: true,
    isScrollCorrection: true,
    theme: theme.PRIMARY_THEME,
    onClick: undefined,
    t: undefined,
};

export { Tab as default };
//# sourceMappingURL=Tab.js.map
