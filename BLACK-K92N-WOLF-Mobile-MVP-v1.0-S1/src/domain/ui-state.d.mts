export type UiState = 'loading' | 'empty' | 'offline' | 'unauthorized' | 'forbidden' | 'notFound' | 'conflict' | 'rateLimited' | 'serverError';
export declare const UI_STATES: readonly UiState[];
export declare function describeState(state: UiState): { title: string; detail: string; retry: boolean };
export declare function classifyHttpStatus(status: number): UiState | null;
export declare function canRetryAutomatically(method: string, status: number): boolean;
