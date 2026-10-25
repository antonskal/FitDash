import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import TopBar from '@/components/layout/TopBar';
import SyncModal from '@/components/sync/SyncModal';
import Dashboard from '@/pages/Dashboard';
import { useAuthStatus, useSettings, useSyncStatus } from '@/hooks/queries';
import { connectSyncStream } from '@/store/sync';

export default function App() {
  const qc = useQueryClient();
  const [syncOpen, setSyncOpen] = useState(false);
  const { data: auth } = useAuthStatus();
  const { data: sync } = useSyncStatus();
  const { data: settings } = useSettings();
  const autoOpened = useRef(false);

  useEffect(() => connectSyncStream(qc), [qc]);

  useEffect(() => {
    if (autoOpened.current || !auth || !sync || !settings) return;
    const empty = (settings.bounds.days ?? 0) === 0;
    if ((auth.state !== 'authenticated' && empty) || (auth.state === 'authenticated' && sync.isFirstSync)) {
      autoOpened.current = true;
      setSyncOpen(true);
    }
  }, [auth, sync, settings]);

  return (
    <div className="min-h-full flex flex-col">
      <TopBar onOpenSync={() => setSyncOpen(true)} />
      <Dashboard onOpenSync={() => setSyncOpen(true)} />
      {syncOpen && <SyncModal onClose={() => setSyncOpen(false)} />}
    </div>
  );
}
