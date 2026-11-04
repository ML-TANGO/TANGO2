import type { BooleanLike } from './types';
/**
 * Resolves a condition that is {@link BooleanLike} or returns {@link BooleanLike} from a function
 * @param condition The condition to resolve
 */
export declare const getConditionResult: (condition: BooleanLike | ((...args: unknown[]) => BooleanLike)) => boolean;
