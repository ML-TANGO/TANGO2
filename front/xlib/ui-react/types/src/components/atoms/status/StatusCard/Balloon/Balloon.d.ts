declare type Props = {
    title?: string;
    description?: string;
};
declare function Balloon({ title, description }: Props): JSX.Element;
declare namespace Balloon {
    var defaultProps: {
        title: undefined;
        description: undefined;
    };
}
export default Balloon;
