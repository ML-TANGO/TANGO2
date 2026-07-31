declare function objParser(): {
    makeOneDepth: (obj: string | {
        [key: string]: any;
    }, splitStr: string) => {} | null;
};
export { objParser };
