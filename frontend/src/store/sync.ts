import { create } from 'zustand';
import type { QueryClient } from '@tanstack/react-query';
import type { SyncLive } from '@/api/types';

interface SyncStreamState {
  live: SyncLive | null;
  connected: boolean;
  setLive: (l: SyncLive) => void;
  setConnected: (c: boolean) => void;
}

export const useSyncStream = create<SyncStreamState>((set) => ({
  live: null,
  connected: false,
  setLive: (live) => set({ live }),
  setConnected: (connected) => set({ connected }),
}));

let source: EventSource | null = null;

/** Open (once) the SSE connection and route events into the store + react-query cache invalidation. */
export function connectSyncStream(queryClient: QueryClient): () => void {
  if (source) return () => undefined;
  const { setLive, setConnected } = useSyncStream.getState();
  let lastDaysDone = -1;

  const open = () => {
    source = new EventSource('/api/sync/events');
    source.onopen = () => setConnected(true);
    source.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects; nothing else to do.
    };
    const handle = (ev: MessageEvent) => {
      try {
        const payload = JSON.parse(ev.data) as SyncLive;
        setLive(payload);
        // Refresh dashboard data periodically while syncing (every 5 days processed) and on completion.
        if (payload.status === 'running' && payload.daysDone !== lastDaysDone && payload.daysDone % 5 === 0) {
          lastDaysDone = payload.daysDone;
          queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'sync' });
        }
        if (payload.type === 'done' || payload.type === 'error' || payload.status === 'ok' || payload.status === 'error' || payload.status === 'cancelled') {
          queryClient.invalidateQueries();
        }
      } catch {
        /* ignore malformed */
      }
    };
    ['snapshot', 'progress', 'log', 'done', 'error'].forEach((t) => source?.addEventListener(t, handle as EventListener));
  };
  open();
  return () => {
    source?.close();
    source = null;
    setConnected(false);
  };
}
