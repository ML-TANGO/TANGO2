import type { FC } from 'react';
import type { ComponentWithConditionPropsWithFunctionChildren } from '../types';
/**
 * If the `<Case />` is the first one to have its condition evaluates to true
 * inside the parent `<Switch />` it will be the only rendered.
 * @param props The props to pass down to the `<Case />` component
 */
declare const Case: FC<ComponentWithConditionPropsWithFunctionChildren>;
export default Case;
