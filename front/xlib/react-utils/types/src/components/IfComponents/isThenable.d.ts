/**
 * The MIT License (MIT)
 *
 * Copyright © `2020` `The Sapphire Community and its contributors`
 *
 * Source: https://github.com/sapphiredev/utilities/blob/main/packages/utilities/src/lib/isThenable.ts
 * Full license: https://github.com/sapphiredev/utilities/blob/main/LICENSE.md
 */
interface Thenable {
    then: Function;
    catch: Function;
}
/**
 * Verify if the input is a function.
 * @param input The function to verify
 */
export declare function isFunction(input: unknown): input is Function;
/**
 * Verify if an object is a promise.
 * @param input The promise to verify
 */
export declare function isThenable(input: unknown): input is Thenable;
export {};
