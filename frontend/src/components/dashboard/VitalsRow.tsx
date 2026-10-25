import Gauge from '@/components/charts/Gauge';
import StatCard from '@/components/charts/StatCard';
import Row from '@/components/layout/Row';
import { useDaily, useOverview } from '@/hooks/queries';
import { C, scoreColor } from '@/lib/colors';
import { hms, km, num, pace, signed, titleCase } from '@/lib/format';
import type { MetricValue } from '@/api/types';

function mv(m: MetricValue | null | undefined): number | null {
  return m?.value ?? null;
}

function race(m: MetricValue | null | undefined): string {
  return hms(m?.value ?? null);
}

export default function VitalsRow() {
  const { data: o, isLoading } = useOverview();
  const { data: daily } = useDaily();
  const r = o?.readiness;
  const p = o?.performance;
  const d = o?.daily;
  const rhrSpark = (daily?.days ?? []).map((x) => x.resting_hr).filter((v): v is number => v != null);
  const stepSpark = (daily?.days ?? []).map((x) => x.total_steps).filter((v): v is number => v != null);
  const hrvStatus = r?.hrv.status ? titleCase(r.hrv.status) : '';
  const bb = r?.bodyBattery;
  const stepGoal = d?.stepGoal || 10000;
  const stepPct = d?.steps != null ? d.steps / stepGoal : null;

  return (
    <Row id="vitals" title="At-a-Glance Vitals, Readiness & Scores" hint={o ? o.date : undefined}>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-12 gap-2">
        <div className="col-span-1 xl:col-span-1 2xl:col-span-2">
          <Gauge
            label="Sleep Score"
            value={r?.sleepScore}
            sub={r?.sleepQualifier ? `${titleCase(r.sleepQualifier)} · ${hms(r.totalSleepS)}` : hms(r?.totalSleepS)}
          />
        </div>
        <div className="col-span-1 xl:col-span-1 2xl:col-span-2">
          <Gauge
            label="Body Battery"
            value={bb?.current}
            thresholds={[
              [0.25, C.red],
              [0.5, C.orange],
              [0.75, C.yellow],
              [1, C.green],
            ]}
            sub={
              bb
                ? `+${bb.charged ?? '—'} charged  −${bb.drained ?? '—'} drained`
                : isLoading
                  ? '…'
                  : '—'
            }
          />
        </div>
        <div className="col-span-1 xl:col-span-1 2xl:col-span-2">
          <Gauge
            label="Training Readiness"
            value={mv(r?.trainingReadiness)}
            sub={titleCase(r?.trainingReadinessLevel?.text) || (r?.recoveryTimeH?.value != null ? `${num(r.recoveryTimeH.value, 0)}h recovery` : '')}
          />
        </div>

        <StatCard
          label="Overnight HRV"
          value={num(r?.hrv.lastNight, 0)}
          unit="ms"
          color={scoreColor(r?.hrv.lastNight, 50, 35)}
          sub={`${hrvStatus || 'baseline'} · 7d ${num(r?.hrv.sevenDayMean ?? r?.hrv.weeklyAvg, 0)} · ${num(r?.hrv.baselineLow)}–${num(r?.hrv.baselineHigh)}`}
        />
        <StatCard
          label="Resting HR"
          value={num(r?.restingHr, 0)}
          unit="bpm"
          color={C.red}
          spark={rhrSpark}
          sub={`7-day avg ${num(r?.restingHr7d, 1)} · stress ${num(r?.avgStress, 0)}`}
        />
        <StatCard
          label="Training Status"
          value={titleCase(r?.trainingStatus?.text) || '—'}
          size="sm"
          sub={`Load ${num(mv(r?.weeklyLoad), 0)} · ACWR ${num(mv(r?.acwr), 2)}`}
        />

        <StatCard label="VO2 Max Run" value={num(mv(p?.vo2maxRunning), 1)} unit="ml/kg/min" color={C.orange} />
        <StatCard label="VO2 Max Bike" value={num(mv(p?.vo2maxCycling), 1)} unit="ml/kg/min" color={C.blue} />
        <StatCard
          label="Endurance Score"
          value={num(mv(p?.enduranceScore), 0)}
          sub={`Hill ${num(mv(p?.hillScore), 0)} · str ${num(mv(p?.hillStrength), 0)} / end ${num(mv(p?.hillEndurance), 0)}`}
        />
        <StatCard
          label="Lactate Threshold"
          value={num(mv(p?.lactateThresholdHr), 0)}
          unit="bpm"
          sub={`Pace ${pace(mv(p?.lactateThresholdSpeedMps))}`}
        />
        <StatCard
          className="col-span-2"
          label="Race Predictions"
          size="sm"
          value={
            <span className="text-sm grid grid-cols-2 gap-x-4 gap-y-0.5">
              <span>5K {race(p?.race['5k'])}</span>
              <span>10K {race(p?.race['10k'])}</span>
              <span>Half {race(p?.race.half)}</span>
              <span>Marathon {race(p?.race.marathon)}</span>
            </span>
          }
        />

        <StatCard
          label="Daily Steps"
          value={num(d?.steps, 0)}
          color={C.green}
          progress={stepPct}
          progressColor={stepPct != null && stepPct >= 1 ? C.green : C.yellow}
          spark={stepSpark}
          sub={`${km(d?.distanceM)} · goal ${num(stepGoal)}`}
        />
        <StatCard
          label="Calories"
          value={num(d?.activeKcal, 0)}
          unit="kcal"
          color={C.orange}
          sub={`Active ${num(d?.activeKcal, 0)} · Resting ${num(d?.restingKcal, 0)}`}
        />
        <StatCard
          label="Hydration"
          value={d?.hydrationMl != null ? num(d.hydrationMl / 1000, 1) : '—'}
          unit="L"
          color={C.cyan}
          progress={d?.hydrationMl != null && d.hydrationGoalMl ? d.hydrationMl / d.hydrationGoalMl : null}
          sub={`Goal ${d?.hydrationGoalMl != null ? num(d.hydrationGoalMl / 1000, 1) + ' L' : '—'} · sweat ${num(d?.sweatLossMl, 0)} ml`}
        />
        <StatCard
          label="Blood Pressure"
          value={
            d?.bloodPressure.systolic?.value != null
              ? `${num(d.bloodPressure.systolic.value, 0)}/${num(d.bloodPressure.diastolic?.value, 0)}`
              : '—'
          }
          unit="mmHg"
          sub={`Pulse ${num(mv(d?.bloodPressure.pulse), 0)} bpm`}
        />
        <StatCard
          label="Body Composition"
          size="sm"
          value={d?.body.weightKg?.value != null ? `${num(d.body.weightKg.value, 1)} kg` : '—'}
          sub={`BMI ${num(mv(d?.body.bmi), 1)} · fat ${num(mv(d?.body.bodyFatPct), 1)}% · muscle ${num(mv(d?.body.muscleMassKg), 1)} kg · bone ${num(mv(d?.body.boneMassKg), 1)} kg`}
        />
        <StatCard
          label="Overnight Δ Skin Temp"
          value={signed(d?.skinTempDevC, 2)}
          unit="°C"
          color={(d?.skinTempDevC ?? 0) > 0.3 ? C.orange : C.cyan}
          sub={`${signed(d?.skinTempDevF, 2)} °F · SpO2 ${num(d?.spo2Avg, 1)}%`}
        />
      </div>
    </Row>
  );
}
