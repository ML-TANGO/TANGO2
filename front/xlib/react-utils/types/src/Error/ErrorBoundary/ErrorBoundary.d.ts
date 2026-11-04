import { Component, ErrorInfo } from 'react';
declare type Props = {
    children: JSX.Element;
    fallback: JSX.Element;
};
declare type State = {
    hasError: boolean;
};
export declare class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props);
    static getDerivedStateFromError(_: Error): State;
    componentDidCatch(error: Error, errorInfo: ErrorInfo): void;
    render(): JSX.Element & import("react").ReactNode;
}
export default ErrorBoundary;
