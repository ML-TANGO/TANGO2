declare type Props = {
    testProp1?: number;
    testProp2?: string;
};
declare function Content({ testProp1, testProp2 }: Props): JSX.Element;
declare namespace Content {
    var defaultProps: {
        testProp1: number;
        testProp2: string;
    };
}
export default Content;
