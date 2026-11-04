declare type Props = {
    testProp1?: string;
    testProp2?: string;
};
declare function Header({ testProp1, testProp2 }: Props): JSX.Element;
declare namespace Header {
    var defaultProps: {
        testProp1: string;
        testProp2: string;
    };
}
export default Header;
