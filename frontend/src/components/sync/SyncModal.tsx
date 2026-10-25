import { FormEvent, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { KeyRound, Loader2, ShieldCheck, X } from 'lucide-react';
import { api, ApiError } from '@/api/client';
import { useAuthStatus, useSettings, useSyncStatus } from '@/hooks/queries';
import { useSyncStream } from '@/store/sync';
import { relative } from '@/lib/format';

interface Props {
  onClose: () => void;
}

const LOOKBACKS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 180, label: '6 months' },
  { days: 365, label: '1 year' },
  { days: 730, label: '2 years' },
  { days: 1095, label: '3 years' },
];

export default function SyncModal({ onClose }: Props) {
  const qc = useQueryClient();
  const { data: auth, isLoading: authLoading } = useAuthStatus();
  const { data: sync } = useSyncStatus();
  const { data: settings } = useSettings();
  const live = useSyncStream((s) => s.live);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfa, setMfa] = useState('');
  const [lookback, setLookback] = useState(sync?.defaults.lookbackDays ?? 90);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const running = live?.status === 'running' || sync?.isRunning;
  const state = auth?.state ?? 'unauthenticated';
  const progress =
    live?.phase === 'activities'
      ? live.activitiesNew
        ? live.activitiesDone / live.activitiesNew
        : 0
      : live?.daysTotal
        ? live.daysDone / live.daysTotal
        : 0;

  const handleErr = (e: unknown) => {
    setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Something went wrong');
  };

  const login = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email.trim(), password);
      await qc.invalidateQueries({ queryKey: ['auth'] });
    } catch (err) {
      handleErr(err);
    } finally {
      setBusy(false);
    }
  };

  const submitMfa = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.mfa(mfa.trim());
      await qc.invalidateQueries({ queryKey: ['auth'] });
    } catch (err) {
      handleErr(err);
    } finally {
      setBusy(false);
    }
  };

  const startSync = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.startSync(sync?.isFirstSync ? { lookbackDays: lookback } : {});
      await qc.invalidateQueries({ queryKey: ['sync'] });
    } catch (err) {
      handleErr(err);
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    await api.cancelSync();
    qc.invalidateQueries({ queryKey: ['sync'] });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="panel w-full max-w-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="sync-title"
      >
        <header className="flex items-center justify-between px-4 h-10 border-b border-edge">
          <h2 id="sync-title" className="text-sm font-semibold">
            Garmin Connect
          </h2>
          <button className="btn btn-ghost px-1.5" onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </header>

        <div className="p-4 space-y-4">
          {authLoading && <p className="text-xs text-ink-faint">Checking session…</p>}

          {state === 'unauthenticated' && (
            <form onSubmit={login} className="space-y-3">
              <p className="text-xs text-ink-dim">
                Tokens are stored locally in <code className="text-ink-faint">{auth?.tokenDir ?? './.garmin_tokens'}</code>.
                Credentials are sent only to Garmin — never stored.
              </p>
              <label className="block text-[11px] text-ink-faint">
                Email
                <input
                  className="input mt-1 w-full"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label className="block text-[11px] text-ink-faint">
                Password
                <input
                  className="input mt-1 w-full"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {error && <p className="text-xs text-red">{error}</p>}
              <button className="btn btn-primary w-full justify-center h-8" disabled={busy} type="submit">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
                Sign in
              </button>
              {(settings?.bounds.days ?? 0) > 0 && (
                <p className="text-[11px] text-ink-faint text-center">
                  Local data is already loaded ({settings?.bounds.days} days). You can close this and browse offline.
                </p>
              )}
            </form>
          )}

          {state === 'needs_mfa' && (
            <form onSubmit={submitMfa} className="space-y-3">
              <p className="text-xs text-ink-dim">{auth?.message ?? 'Enter the one-time code Garmin sent you.'}</p>
              <label className="block text-[11px] text-ink-faint">
                MFA code
                <input
                  className="input mt-1 w-full tracking-[0.3em] text-center text-lg"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  value={mfa}
                  onChange={(e) => setMfa(e.target.value)}
                />
              </label>
              {error && <p className="text-xs text-red">{error}</p>}
              <button className="btn btn-primary w-full justify-center h-8" disabled={busy} type="submit">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                Verify
              </button>
            </form>
          )}

          {state === 'authenticated' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <div>
                  <div className="text-ink font-medium">{auth?.displayName ?? auth?.email ?? 'Signed in'}</div>
                  <div className="text-ink-faint">Last synced {relative(sync?.lastSyncedAt)}</div>
                </div>
                <span className="text-[10px] uppercase tracking-wider text-emerald">Connected</span>
              </div>

              {sync?.isFirstSync && !running && (
                <div>
                  <div className="text-[11px] text-ink-faint mb-1.5">Initial lookback window</div>
                  <div className="flex flex-wrap gap-1">
                    {LOOKBACKS.map((o) => (
                      <button
                        key={o.days}
                        type="button"
                        className={`pill ${lookback === o.days ? 'pill-active' : ''}`}
                        onClick={() => setLookback(o.days)}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-ink-faint">
                    First sync backfills {lookback} days, then every launch fetches only the watermark → today.
                  </p>
                </div>
              )}

              {sync?.plan && !running && (
                <p className="text-[11px] text-ink-dim num">
                  Next: {sync.plan.mode} {sync.plan.startDate} → {sync.plan.endDate} ({sync.plan.days} days)
                </p>
              )}

              {running && (
                <div className="space-y-2">
                  <div className="h-1.5 rounded-full bg-edge overflow-hidden">
                    <div className="h-full bg-blue transition-all" style={{ width: `${Math.min(100, progress * 100)}%` }} />
                  </div>
                  <p className="text-xs text-ink num">{live?.message || 'Syncing…'}</p>
                  <p className="text-[11px] text-ink-faint num">
                    {live?.phase === 'activities'
                      ? `Activities ${live.activitiesDone}/${live.activitiesNew}`
                      : `${live?.daysDone ?? 0}/${live?.daysTotal ?? 0} days`}
                    {live?.errors ? ` · ${live.errors} warnings` : ''}
                  </p>
                </div>
              )}

              {live?.recentLog && live.recentLog.length > 0 && (
                <pre className="max-h-36 overflow-auto text-[10px] leading-4 text-ink-dim font-mono bg-carbon border border-edge rounded-sm p-2">
                  {live.recentLog.slice(-12).join('\n')}
                </pre>
              )}

              {error && <p className="text-xs text-red">{error}</p>}
              {live?.status === 'error' && live.error && <p className="text-xs text-red">{live.error}</p>}

              <div className="flex gap-2">
                {running ? (
                  <button className="btn w-full justify-center" onClick={cancel}>
                    Cancel sync
                  </button>
                ) : (
                  <button className="btn btn-primary w-full justify-center h-8" onClick={startSync} disabled={busy}>
                    {busy ? <Loader2 size={14} className="animate-spin" /> : null}
                    {sync?.isFirstSync ? 'Start initial sync' : 'Sync latest'}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
