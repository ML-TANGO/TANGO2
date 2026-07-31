declare const rootReducer: import("redux").Reducer<import("redux").CombinedState<{
    modal: import("./modules/modal").ModalState;
    fmodal: import("./modules/flexibleModal").FModalState;
}>, import("redux").AnyAction>;
export default rootReducer;
export declare type RootState = ReturnType<typeof rootReducer>;
