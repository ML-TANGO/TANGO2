import { Properties as CSSProperties } from 'csstype';
declare type RunningType = 'running' | 'trainingRunning' | 'deploymentRunning' | 'active' | 'serviceActive' | 'ready' | 'attached' | 'connected' | 'complete' | 'green';
declare type PendingType = 'pending' | 'reserved' | 'installing' | 'attaching' | 'yellow';
declare type DoneType = 'done' | 'stop' | 'detached' | 'disconnected' | 'gray';
declare type ErrorType = 'expired' | 'failed' | 'error' | 'red';
declare type UnknownType = 'unknown' | 'orange';
declare type InProgressType = 'training' | 'aggregation' | 'broadcasting' | 'idle' | 'blue';
interface StatusCardArgs {
    text: string;
    status: RunningType | PendingType | DoneType | ErrorType | UnknownType | InProgressType;
    size: 'x-small' | 'small' | 'medium' | 'large';
    type: 'help' | 'default';
    theme: ThemeType;
    isTooltip: boolean;
    customStyle?: CSSProperties;
    tooltipData?: {
        title?: string;
        description?: string;
    };
}
export { StatusCardArgs, RunningType, PendingType, DoneType, ErrorType, UnknownType, InProgressType, };
