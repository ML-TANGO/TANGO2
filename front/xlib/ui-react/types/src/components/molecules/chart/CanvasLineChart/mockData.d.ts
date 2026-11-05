declare const singleLineChartMockData: {
    series: {
        left: {
            color: string;
            name: string;
            lineWidth: number;
            series: number[];
        }[];
    };
    axis: {
        bottom: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
            data: number[];
        };
        left: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
        };
    };
};
declare const multiLineChartMockData: {
    series: {
        left: {
            color: string;
            name: string;
            lineWidth: number;
            series: number[];
        }[];
    };
    axis: {
        bottom: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
            data: number[];
        };
        left: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
        };
    };
};
declare const multiAxisChart: {
    series: {
        left: {
            color: string;
            name: string;
            lineWidth: number;
            series: number[];
        }[];
        right: {
            series: number[];
            name: string;
            lineWidth: number;
            color: string;
        }[];
    };
    axis: {
        bottom: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
            data: number[];
        };
        left: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
        };
        right: {
            unitsPerTick: number;
            tickSize: number;
            color: string;
        };
    };
};
export { singleLineChartMockData, multiLineChartMockData, multiAxisChart };
