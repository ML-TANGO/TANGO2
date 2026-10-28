import { __assign } from '../../../../../../_virtual/_tslib.js';
import { jsx, jsxs, Fragment } from 'react/jsx-runtime';
import { theme } from '../../../../../utils/utils.js';
import classNames from '../../../../../../modules/classnames/bind.js';
import style from './NavItem.module.scss.js';

var cx = classNames.bind(style);
function NavItem(_a) {
    var name = _a.name, path = _a.path, Icon = _a.icon, ActiveIcon = _a.activeIcon, group = _a.group, subGroup = _a.subGroup, isGroup = _a.isGroup, onNavigate = _a.onNavigate, theme = _a.theme, excludeChildren = _a.excludeChildren;
    var target = path.split('/').slice(-1)[0];
    var currentPath = window.location.href;
    var end = currentPath.split('/').slice(-1)[0];
    // Flightbase: 메뉴 없는 상세 페이지 상위 메뉴에 매칭
    if (end === 'files') {
        end = 'datasets';
    }
    else if (end === 'test') {
        end = 'services';
    }
    else if (end === 'worker') {
        end = 'workers';
    }
    else if (['llmplayground', 'playgroundmonitor'].includes(end)) {
        end = 'llmplayground';
    }
    else if (['promptinfo', 'promptcommit'].includes(end)) {
        end = 'prompt';
    }
    // end-match 는 isActive 와 별개로 !important 점등을 건다(메뉴 없는 상세 페이지를 상위
    // 메뉴에 매칭하려고 end 를 되매핑한다 — 예: .../files → datasets). 그 되매핑 때문에
    // excludeChildren 로 제외한 하위의 상세 페이지에서 다시 점등되므로 여기서도 끊는다.
    var endMatch = end === target;
    if (endMatch && excludeChildren && excludeChildren.length) {
        var pathname = window.location.pathname;
        // 아래 isActive 의 제외 판정은 react-router match(기본 sensitive:false)를 거쳐
        // 대소문자를 무시한다. 같은 함수 안에서 같은 문제를 푸는 두 판정이 갈리지 않게
        // 여기서도 무시한다(slice 는 원본으로 — ASCII 경로라 소문자화가 길이를 안 바꾼다).
        if (pathname.toLowerCase().indexOf((path + '/').toLowerCase()) === 0) {
            var head = (pathname
                .slice(path.length)
                .split('/')
                .filter(Boolean)[0] || '').toLowerCase();
            if (head &&
                excludeChildren.some(function (c) {
                    return String(c).toLowerCase() === head;
                })) {
                endMatch = false;
            }
        }
    }
    return (jsx("div", __assign({ className: cx('nav-item', group && 'main-group', subGroup && 'sub-group', isGroup && 'group-head', theme, endMatch && 'end-match') }, { children: onNavigate({
            element: (jsxs(Fragment, { children: [Icon &&
                        ActiveIcon &&
                        (typeof Icon === 'function' ? (jsxs("span", __assign({ className: cx('icon-wrap') }, { children: [jsx(ActiveIcon, { className: cx('active-ico') }), jsx(Icon, { className: cx('ico') })] }))) : (jsxs("span", __assign({ className: cx('icon-wrap') }, { children: [jsx("img", { className: cx('active-ico'), src: ActiveIcon, alt: "".concat(name, " link") }), jsx("img", { className: cx('ico'), src: Icon, alt: "".concat(name, " link") })] })))), jsx("span", __assign({ className: cx('text', isGroup && 'blue') }, { children: name }))] })),
            path: path,
            activeClassName: cx('active'),
            isActive: function (match) {
                if (match) {
                    var depth = match.path.split('/').length;
                    if (!match.isExact && depth === 4) {
                        return false;
                    }
                    // 상위 항목은 하위 페이지에서도 점등 유지하되, 섹션 소속이 아닌 별개 목적지
                    // (예: 드라이브 /datasets/management)로 인한 prefix 오점등만 제외.
                    // excludeChildren = 제외할 하위 첫 세그먼트 목록(앱이 nav 항목에 지정).
                    // isGroup 게이트를 두지 않는다 — 그룹 헤드가 아닌 평면 항목('데이터')도
                    // 같은 오점등을 겪고, 그 항목에 isGroup 을 붙이면 group-head 클래스와
                    // 글자색(blue)까지 바뀐다. 지정한 항목만 영향받는 opt-in 이라 안전하다.
                    if (!match.isExact && excludeChildren && excludeChildren.length) {
                        // v5 라우팅은 기본 대소문자 무시 → 세그먼트/제외목록을 소문자 정규화해 비교.
                        var restHead = (window.location.pathname
                            .slice(match.url.length)
                            .split('/')
                            .filter(Boolean)[0] || '').toLowerCase();
                        var excluded = excludeChildren.some(function (c) {
                            return String(c).toLowerCase() === restHead;
                        });
                        if (restHead && excluded) {
                            return false;
                        }
                    }
                }
                return match !== null;
            },
        }) })));
}
NavItem.defaultProps = {
    theme: theme.PRIMARY_THEME,
};

export { NavItem as default };
//# sourceMappingURL=NavItem.js.map
