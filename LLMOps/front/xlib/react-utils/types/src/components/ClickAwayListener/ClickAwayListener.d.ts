import { HTMLAttributes } from 'react';
declare type FocusEvents = 'focusin' | 'focusout';
declare type MouseEvents = 'click' | 'mousedown' | 'mouseup';
declare type TouchEvents = 'touchstart' | 'touchend';
declare type Events = FocusEvent | MouseEvent | TouchEvent;
interface Props extends HTMLAttributes<HTMLElement> {
    onClickAway: (event: Events) => void;
    focusEvent?: FocusEvents;
    mouseEvent?: MouseEvents;
    touchEvent?: TouchEvents;
    children: JSX.Element;
}
/**
 * children의 외부 영역 클릭 시 이벤트가 발생하는 컴포넌트
 * @link https://github.com/ooade/react-click-away-listener
 * @license MIT License
 * @author ooade
 * @version 22-02-04
 */
declare function ClickAwayListener({ children, onClickAway, focusEvent, mouseEvent, touchEvent, }: Props): JSX.Element;
declare namespace ClickAwayListener {
    var displayName: string;
}
export default ClickAwayListener;
