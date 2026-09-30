import { Card, Chip, InfoTip, NeedsAnalysis, PageHead, Ring, StepFooter, Badge } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { capName, gapReason, levelName, roleTitle } from '../lib/compose';
import { useApp } from '../state';

const COLS = [
  ['verified', 'var(--good)'],
  ['developing', 'var(--warn)'],
  ['missing', 'var(--bad)'],
] as const;

export default function Gaps() {
  const i18n = useI18n();
  const { t } = i18n;
  const { run } = useApp();
  const pw = run?.values?.pathway;
  const roleId = run?.values?.selected_role_id;
  useVisit('/gaps', !!pw);
  const total = pw ? pw.counts.verified + pw.counts.developing + pw.counts.missing : 0;
  return (
    <>
      <PageHead step="gaps" icon="map-2" title={t('gaps.title')} sub={roleId ? t('gaps.sub', { role: roleTitle(i18n, roleId, roleId) }) : t('gaps.sub_none')} actions={<InfoTip><b>{t('gaps.info_title')}</b><p>{t('gaps.info')}</p></InfoTip>} />
      <NeedsAnalysis ready={!!pw}>
        {pw && (
          <>
            <Card className="gaps-summary">
              <Ring parts={COLS.map(([k, c]) => ({ value: pw.counts[k], color: c }))} label={<><b>{pw.counts.verified}/{total}</b><span>{t('status.verified')}</span></>} />
              <div className="legend">
                {COLS.map(([k, c]) => (
                  <div key={k}><span className="dot" style={{ background: c }} /><b>{pw.counts[k]}</b> {t('status.' + k)}<small>{t('gaps.legend_' + k)}</small></div>
                ))}
              </div>
            </Card>
            <div className="grid cols-3 stagger">
              {COLS.map(([k], ci) => (
                <Card key={k} title={<>{t('status.' + k)} <Chip tone={k === 'verified' ? 'good' : k === 'developing' ? 'warn' : 'bad'}>{pw.counts[k]}</Chip></>} className={`gap-col ${k}`} style={{ ['--i' as any]: ci }}>
                  {pw.gaps.filter((g: any) => g.status === k).map((g: any) => (
                    <div key={g.capability} className="gap-item" data-testid={`gap-${g.capability}`}>
                      <div className="gap-top"><b>{capName(i18n, g.capability, g.capability_name)}</b><Chip>{levelName(i18n, g.required_level)}</Chip></div>
                      <p className="muted small">{gapReason(i18n, g)}</p>
                      {g.evidence?.source_id && <div className="chip-row tight"><Badge status={g.evidence.verification_status} /><span className="small muted">{g.evidence.source_id}</span></div>}
                    </div>
                  ))}
                  {pw.gaps.filter((g: any) => g.status === k).length === 0 && <p className="muted">—</p>}
                </Card>
              ))}
            </div>
          </>
        )}
      </NeedsAnalysis>
      {pw && <StepFooter step="gaps" />}
    </>
  );
}
