declare type Props = {
    testProp1?: string;
    testProp2?: string;
};
declare function Footer({ testProp1, testProp2 }: Props): JSX.Element;
declare namespace Footer {
    var defaultProps: {
        testProp1: string;
        testProp2: string;
    };
}
export default Footer;
