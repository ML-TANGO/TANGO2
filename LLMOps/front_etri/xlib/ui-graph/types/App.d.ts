import '@src/style/style.scss';
declare function App(): {
    tagName: string;
    props: {
        className: string;
    };
    childNode: ({
        tagName: string;
        childNode: string;
        props: {
            className: string;
        };
    } | {
        tagName: string;
        props: {
            className: string;
        };
        childNode: {
            tagName: string;
            props: {
                className: string;
            };
            childNode: ({
                tagName: string;
                props: {
                    className: string;
                };
                childNode: ({
                    tagName: string;
                    props: {
                        className: string;
                        id: string;
                    };
                    childNode: string;
                } | {
                    tagName: string;
                    props: {
                        className: string;
                        id?: undefined;
                    };
                    childNode: string;
                })[];
            } | {
                tagName: string;
                props: {
                    className: string;
                };
                childNode: ({
                    tagName: string;
                    props: {
                        className: string;
                    };
                    childNode: {
                        tagName: string;
                        props: {
                            className: string;
                        };
                        childNode: string;
                        event: {
                            type: string;
                            eventFunc: () => void;
                        };
                    }[];
                } | {
                    tagName: string;
                    props: {
                        className: string;
                    };
                    childNode: string;
                })[];
            })[];
        }[];
    })[];
};
export default App;
