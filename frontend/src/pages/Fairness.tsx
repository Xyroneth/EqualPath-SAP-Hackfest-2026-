import { Button, Icon, Input, Option, Select, TextArea } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { Badge, Card, Chip, EmptyState, ErrorNote, InfoTip, NeedsAnalysis, Note, PageHead, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { roleTitle, slug } from '../lib/compose';
import { useApp } from '../state';

const NEVER = ['name', 'gender', 'age', 'disability', 'college', 'career_break'];
const FEATURES = ['languages', 'commute_city', 'work_modes', 'can_relocate', 'weekly_learning_hours', 'relevant_experience_years', 'schedule_needs'];
const TWIN_ICON: Record<string, string> = {
  man: 'male', woman: 'female', break_added: 'history', name_community: 'person-placeholder', age_young: 'calendar', age_older: 'calendar', break_none: 'history', break_long: 'history',
  disability: 'accessibility', college: 'education', hometown: 'map',
};
const PERT_KEY: Record<string, string> = { display_name: 'name', gender: 'gender', age: 'age', career_break: 'career_break', disability: 'disability', college: 'college' };
const TRY_FIELDS = ['age', 'career_break_years', 'college', 'name', 'gender', 'disability', 'hometown'] as const;
const GENDERS = ['female', 'male', 'non_binary', 'other'];
const fmt = (n: number) => (Math.round(n * 10) / 10).toFixed(1);
const signed = (n: number) => (n > 0 ? '+' : '') + fmt(n);

type System = 'equalpath' | 'biased';

export default function Fairness() {
  const i18n = useI18n();
  const { t, tf } = i18n;
  const { run, runId, role, toast } = useApp();
  const [mon, setMon] = useState<any>(null);
  const [review, setReview] = useState<any>(undefined);
  const [finding, setFinding] = useState<'no_concerns' | 'concern' | ''>('');
  const [note, setNote] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [system, setSystem] = useState<System>('equalpath');
  const [tryField, setTryField] = useState<(typeof TRY_FIELDS)[number]>('age');
  const [tryValue, setTryValue] = useState('');
  const [tryRes, setTryRes] = useState<any>(null);
  const [tryErr, setTryErr] = useState<string | null>(null);
  const [trying, setTrying] = useState(false);
  const b = run?.values?.bias_audit;
  useVisit('/fairness', !!b);
  useEffect(() => {
    api.get('/api/bias/monitoring-prototype').then(setMon).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (runId && b) api.get(`/api/runs/${runId}/fairness-review`).then((r) => setReview(r.review)).catch(() => setReview(null));
  }, [runId, !!b, role]); // eslint-disable-line react-hooks/exhaustive-deps

  const value = (field: string, v: any): string => {
    if (v === null || v === undefined || v === '') {
      if (field === 'college') return t('fair.v_not_named');
      if (field === 'disability') return t('fair.v_none');
      // Staff without evidence access never receive the person's real details; for the person themselves, blank means "not given".
      return role === 'candidate' || role === 'counsellor' ? t('fair.v_not_given') : t('fair.v_hidden');
    }
    if (field === 'gender') return tf('gender.' + v, String(v));
    if (field === 'career_break') return Number(v) === 0 ? t('fair.v_none') : t('fair.v_years', { n: Math.round(Number(v) / 12) });
    return String(v);
  };
  const ruleText = (r: any) => t('fair.why_rule', { rule: t('fair.rule_' + r.code), pts: signed(r.points) });
  const sign = async () => {
    setErr(null);
    if (!finding || note.trim().length < 5) return setErr(t('fair.err_signoff'));
    try {
      setReview(await api.post(`/api/runs/${runId}/fairness-review`, { finding, note }));
      toast(t('fair.signed'), 'success');
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const runTry = async () => {
    setTryErr(null);
    const v = tryField === 'gender' ? tryValue || 'male' : tryValue;
    if (!v.trim()) return setTryErr(t('fair.try_err'));
    setTrying(true);
    try {
      setTryRes(await api.post(`/api/runs/${runId}/fairness/try`, { field: tryField, value: v }));
    } catch (e: any) {
      setTryErr(e.message);
      setTryRes(null);
    } finally {
      setTrying(false);
    }
  };

  const base = b?.baseline;
  const selected = base?.selected_role_id;
  const selTitle = selected ? roleTitle(i18n, selected, base.ranking.find((r: any) => r.role_id === selected)?.title ?? selected) : '';
  const twins: any[] = b?.counterfactuals ?? [];
  const oursChanged = twins.filter((x) => x.material_change).length;
  const refChanged = twins.filter((x) => x.reference?.would_flag).length;
  const biased = system === 'biased';
  const changed = (x: any) => (biased ? !!x.reference?.would_flag : !!x.material_change);

  return (
    <>
      <PageHead step="fairness" icon="compare" title={t('fair.title')} sub={t('fair.sub2')} actions={<InfoTip><b>{t('fair.info_title')}</b><p>{t('fair.info2')}</p></InfoTip>} />
      <NeedsAnalysis ready={!!b}>
        {b && !base && <EmptyState kind="analysis" title={t('common.old_run')} text={t('common.old_run_text')} />}
        {b && base && (
          <>
            {/* ---- how it works */}
            <ol className="how3" aria-label={t('fair.how_title')}>
              <li><span className="how-n">1</span><Icon name="copy" aria-hidden="true" /><b>{t('fair.how_1', { n: twins.length })}</b><small>{t('fair.how_1d')}</small></li>
              <li><span className="how-n">2</span><Icon name="edit" aria-hidden="true" /><b>{t('fair.how_2')}</b><small>{t('fair.how_2d')}</small></li>
              <li><span className="how-n">3</span><Icon name="compare" aria-hidden="true" /><b>{t('fair.how_3')}</b><small>{t('fair.how_3d')}</small></li>
            </ol>

            {/* ---- which system is being checked: every card below follows this choice */}
            <section className="sys-switch" aria-labelledby="sys-title">
              <h3 id="sys-title">{t('fair.sys_title')}</h3>
              <div className="sys-options" role="radiogroup" aria-labelledby="sys-title">
                <button type="button" role="radio" aria-checked={!biased} className={`sys-card ${oursChanged ? 'bad' : 'good'} ${!biased ? 'on' : ''}`} onClick={() => setSystem('equalpath')} data-testid="system-equalpath">
                  <span className="sys-ico"><Icon name="shield" aria-hidden="true" /></span>
                  <span className="sys-text"><b>{t('fair.sys_ours')}</b><small>{t('fair.sys_ours_d')}</small></span>
                  <span className="sys-count">{t('fair.sys_changed', { n: oursChanged, total: twins.length })}</span>
                </button>
                <button type="button" role="radio" aria-checked={biased} className={`sys-card ${refChanged ? 'bad' : 'good'} ${biased ? 'on' : ''}`} onClick={() => setSystem('biased')} data-testid="system-biased">
                  <span className="sys-ico"><Icon name="lab" aria-hidden="true" /></span>
                  <span className="sys-text"><b>{t('fair.sys_ref')}</b><small>{t('fair.sys_ref_d')}</small></span>
                  <span className="sys-count">{t('fair.sys_changed', { n: refChanged, total: twins.length })}</span>
                </button>
              </div>
            </section>

            <div className={`verdict ${(biased ? refChanged : !b.passed) ? 'fail' : 'pass'}`} data-testid="bias-result">
              <span className="verdict-icon"><Icon name={(biased ? refChanged : !b.passed) ? 'alert' : 'shield'} aria-hidden="true" /></span>
              <div>
                {biased ? (
                  <><h2>{t('fair.ref_verdict', { n: refChanged, total: twins.length })}</h2><p>{t('fair.ref_verdict_text')}</p></>
                ) : (
                  <><h2>{b.passed ? t('fair.passed_big') : t('fair.failed')}</h2>
                    <p>{b.passed ? t('fair.passed_text2', { n: twins.length, role: selTitle, score: fmt(base.selected_score) }) : t('fair.failed_text', { n: b.material_count ?? 0 })}</p></>
                )}
              </div>
              {!biased && review && <Chip tone={review.finding === 'concern' ? 'bad' : 'good'} icon="inspect">{t('fair.audited_' + review.finding)}</Chip>}
            </div>

            {biased && (
              <Note tone="warn" icon="lab">
                <b>{t('fair.ref_note')}</b>
                <ul className="ref-rules">{b.reference_filter?.rules?.map((r: any) => <li key={r.code}>{t('fair.rule_' + r.code)}</li>)}</ul>
                <Chip tone="warn">{t('fair.simulated')}</Chip>
              </Note>
            )}

            {/* ---- the starting point */}
            <Card title={t('fair.baseline_title')} icon="target-group">
              {!biased ? (
                <>
                  <p className="muted small">{t('fair.baseline_sub')}</p>
                  <div className="base-rank">
                    {base.ranking.map((r: any, i: number) => (
                      <div key={r.role_id} className={`base-row ${r.role_id === selected ? 'sel' : ''}`}>
                        <span className="base-n">{i + 1}</span>
                        <span className="base-t">{roleTitle(i18n, r.role_id, r.title)}{r.role_id === selected && <Chip tone="accent">{t('fair.chosen')}</Chip>}</span>
                        <span className="base-bar"><span style={{ width: `${r.score}%` }} /></span>
                        <b className="mono">{fmt(r.score)}</b>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="ref-base" data-testid="ref-baseline">
                  <p className="muted small">{t('fair.ref_base_sub', { role: selTitle })}</p>
                  <ul>
                    <li><span>{t('fair.ref_base_skills')}</span><b className="mono">{fmt(base.selected_score)}</b></li>
                    {(base.reference_rules ?? []).map((r: any) => <li key={r.code} className="bad"><span>{t('fair.rule_' + r.code)}</span><b className="mono">{signed(r.points)}</b></li>)}
                    {!base.reference_rules && <li className="muted"><span>{t('fair.ref_base_hidden')}</span><b /></li>}
                    <li className="total"><span>{t('fair.ref_base_total')}</span><b className="mono">{fmt(base.reference_score)}</b></li>
                  </ul>
                </div>
              )}
            </Card>

            {/* ---- the twins */}
            <Card title={t('fair.twins_title', { n: twins.length })} icon="group">
              <p className="muted small">{biased ? t('fair.twins_sub_ref') : t('fair.twins_sub')}</p>
              <div className="twin-grid stagger" key={system}>
                {twins.map((x) => (
                  <article key={x.id} className={`twin ${changed(x) ? 'bad' : 'good'}`} data-testid={`twin-${x.id}`}>
                    <header>
                      <span className="twin-ico"><Icon name={TWIN_ICON[x.id] ?? 'person-placeholder'} aria-hidden="true" /></span>
                      <div><b>{t('tw.' + x.id)}</b><small>{t('fair.why_' + x.why)}</small></div>
                    </header>
                    <dl className="twin-diff">
                      {x.diff.map((d: any) => (
                        <div key={d.field}>
                          <dt>{t('fair.f_' + d.field)}</dt>
                          <dd><span className="was">{value(d.field, d.before)}</span><Icon name="arrow-right" aria-hidden="true" /><b>{value(d.field, d.after)}</b></dd>
                        </div>
                      ))}
                    </dl>
                    <div className="twin-score">
                      <span>{biased ? t('fair.score_ref') : t('fair.score_for', { role: selTitle })}</span>
                      <b className="mono">{biased ? `${fmt(x.reference.before)} → ${fmt(x.reference.after)}` : `${fmt(x.selected_score_before)} → ${fmt(x.selected_score_after)}`}</b>
                    </div>
                    {biased ? (
                      <ul className="twin-checks">
                        {x.reference.reasons?.length
                          ? x.reference.reasons.map((r: any) => <li key={r.code} className="bad"><Icon name="alert" aria-hidden="true" />{ruleText(r)}</li>)
                          : <li className="good"><Icon name="accept" aria-hidden="true" />{t('fair.ref_no_rule')}</li>}
                      </ul>
                    ) : (
                      <ul className="twin-checks">
                        <li className={x.top_role_same ? 'good' : 'bad'}><Icon name={x.top_role_same ? 'accept' : 'decline'} aria-hidden="true" />{x.top_role_same ? t('fair.top_same') : t('fair.top_changed')}</li>
                        <li className={x.ranking_changed ? 'bad' : 'good'}><Icon name={x.ranking_changed ? 'decline' : 'accept'} aria-hidden="true" />{x.ranking_changed ? t('fair.order_changed') : t('fair.order_same')}</li>
                        <li className={x.extraction_changed ? 'bad' : 'good'}><Icon name={x.extraction_changed ? 'decline' : 'accept'} aria-hidden="true" />
                          {x.extraction_rechecked ? t('fair.skills_same', { a: x.skills_before, b: x.skills_after }) : t('fair.docs_same')}</li>
                      </ul>
                    )}
                    <div className="twin-result">
                      {changed(x)
                        ? <Badge status="failed" label={t('fair.diff_pts', { d: biased ? signed(x.reference.delta) : signed(x.selected_score_after - x.selected_score_before) })} />
                        : <Badge status="completed" label={t('fair.same_diff', { d: fmt(biased ? x.reference.delta : x.max_score_delta) })} />}
                    </div>
                  </article>
                ))}
              </div>
            </Card>

            {/* ---- try your own twin: both systems, live */}
            <Card title={t('fair.try_title')} icon="edit" className="try-card">
              <p className="muted small">{t('fair.try_sub')}</p>
              <div className="try-fields" role="radiogroup" aria-label={t('fair.try_field')}>
                {TRY_FIELDS.map((f) => (
                  <button key={f} type="button" role="radio" aria-checked={tryField === f} className={tryField === f ? 'on' : ''}
                    onClick={() => { setTryField(f); setTryValue(''); setTryRes(null); setTryErr(null); }} data-testid={`try-field-${f}`}>{t('fair.f_' + f)}</button>
                ))}
              </div>
              <div className="try-row">
                {tryField === 'gender' ? (
                  <Select accessibleName={t('fair.try_value')} onChange={(e) => setTryValue(e.detail.selectedOption.getAttribute('value')!)} data-testid="try-value">
                    {GENDERS.map((g) => <Option key={g} value={g} selected={(tryValue || 'male') === g}>{tf('gender.' + g, g)}</Option>)}
                  </Select>
                ) : (
                  <Input value={tryValue} placeholder={t('fair.try_ph_' + tryField)} onInput={(e: any) => setTryValue(e.target.value)}
                    onKeyDown={(e: any) => e.key === 'Enter' && runTry()} accessibleName={t('fair.try_value')} data-testid="try-value" />
                )}
                <Button design="Emphasized" icon="compare" onClick={runTry} disabled={trying} data-testid="try-run">{t('fair.try_run')}</Button>
              </div>
              {tryField === 'hometown' && <p className="muted small">{t('fair.try_hometown_note')}</p>}
              <ErrorNote error={tryErr} />
              {tryRes && (
                <div className="try-result" data-testid="try-result">
                  <p className="try-diff">{tryRes.diff.map((d: any) => <span key={d.field}>{t('fair.f_' + d.field)}: <s>{value(d.field, d.before)}</s> → <b>{value(d.field, d.after)}</b></span>)}</p>
                  <div className="try-cols">
                    <div className={`try-col ${tryRes.material_change ? 'bad' : 'good'}`} data-testid="try-result-ours">
                      <span className="try-sys"><Icon name="shield" aria-hidden="true" /> {t('fair.sys_ours')}</span>
                      <b className="mono big">{fmt(tryRes.selected_score_before)} → {fmt(tryRes.selected_score_after)}</b>
                      <Badge status={tryRes.material_change ? 'failed' : 'completed'} label={tryRes.material_change ? t('fair.diff_pts', { d: signed(tryRes.selected_score_after - tryRes.selected_score_before) }) : t('fair.try_same')} />
                      <small>{tryRes.material_change ? t('fair.try_ours_bad') : t('fair.try_ours_good')}</small>
                    </div>
                    <div className={`try-col ${tryRes.reference.would_flag ? 'bad' : 'good'}`} data-testid="try-result-ref">
                      <span className="try-sys"><Icon name="lab" aria-hidden="true" /> {t('fair.sys_ref')}</span>
                      <b className="mono big">{fmt(tryRes.reference.before)} → {fmt(tryRes.reference.after)}</b>
                      <Badge status={tryRes.reference.would_flag ? 'failed' : 'completed'} label={tryRes.reference.would_flag ? t('fair.diff_pts', { d: signed(tryRes.reference.delta) }) : t('fair.try_same')} />
                      <small>{tryRes.reference.reasons?.length ? tryRes.reference.reasons.map(ruleText).join(' ') : t('fair.ref_no_rule')}</small>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* ---- what the match can and cannot see */}
            <div className="grid cols-2">
              <Card title={t('fair.uses')} icon="filter">
                <div className="chip-row">{FEATURES.map((f) => <Chip key={f} tone="good">{t('feat.' + f)}</Chip>)}</div>
                <h4>{t('fair.never')}</h4>
                <div className="chip-row">{NEVER.map((f) => <Chip key={f} tone="bad" icon="decline">{t('never.' + f)}</Chip>)}</div>
              </Card>
              <Card title={t('fair.perturb_title')} icon="synchronize">
                <p className="muted small">{t('fair.perturb_sub')}</p>
                <table className="tbl compact">
                  <thead><tr><th>{t('fair.p_detail')}</th><th>{t('fair.p_values')}</th><th>{t('fair.p_change')}</th></tr></thead>
                  <tbody>{b.feature_audit.perturbation.map((p: any) => (
                    <tr key={p.attribute}><td>{t('never.' + (PERT_KEY[p.attribute] ?? p.attribute))}</td><td>{p.values_tested}</td>
                      <td className={p.contribution === 0 ? 'good-text' : 'bad-text'}><b>{p.contribution === 0 ? '0.0' : '≠ 0'}</b></td></tr>
                  ))}</tbody>
                </table>
              </Card>
            </div>
            <Note tone="warn" icon="hint">{t('fair.limit')}</Note>

            {/* ---- auditor sign-off */}
            <Card title={t('fair.signoff_title')} icon="inspect" className="signoff-card">
              <span id="signoff" className="anchor" />
              {review ? (
                <div className={`signoff-done ${review.finding}`} data-testid="fairness-signoff">
                  <Icon name={review.finding === 'concern' ? 'alert' : 'accept'} aria-hidden="true" />
                  <div><b>{t('fair.audited_' + review.finding)}</b><p>“{review.note}”</p><small className="muted">{review.actor} · {(review.at ?? '').slice(0, 16).replace('T', ' ')} UTC</small></div>
                </div>
              ) : role === 'auditor' ? (
                <>
                  <p className="muted small">{t('fair.signoff_sub')}</p>
                  <div className="res-choice" role="radiogroup" aria-label={t('fair.signoff_title')}>
                    <button type="button" role="radio" aria-checked={finding === 'no_concerns'} className={finding === 'no_concerns' ? 'on' : ''} onClick={() => setFinding('no_concerns')} data-testid="finding-no_concerns"><Icon name="accept" /> {t('fair.f_no_concerns')}</button>
                    <button type="button" role="radio" aria-checked={finding === 'concern'} className={finding === 'concern' ? 'on bad' : ''} onClick={() => setFinding('concern')} data-testid="finding-concern"><Icon name="alert" /> {t('fair.f_concern')}</button>
                  </div>
                  <TextArea rows={2} value={note} placeholder={t('fair.signoff_note')} onInput={(e: any) => setNote(e.target.value)} accessibleName={t('fair.signoff_note')} data-testid="finding-note" />
                  <ErrorNote error={err} />
                  <Button design="Emphasized" icon="inspect" onClick={sign} data-testid="finding-submit">{t('fair.signoff_submit')}</Button>
                </>
              ) : (
                <p className="muted">{t('fair.signoff_none')}</p>
              )}
            </Card>
          </>
        )}
      </NeedsAnalysis>
      {mon && (
        <details className="monitor">
          <summary>{t('fair.monitor')} <Chip tone="warn">{t('fair.sample')}</Chip></summary>
          <p className="muted small">{t('fair.monitor_text')}</p>
          <div className="scroll-x">
            <table className="tbl">
              <thead><tr><th>{t('fair.m_group')}</th><th>n</th><th>{t('fair.m_reco')}</th><th>{t('fair.m_appr')}</th><th>{t('fair.m_ratio')}</th><th></th></tr></thead>
              <tbody>
                {mon.groups.map((g: any) => (
                  <tr key={g.dimension + g.group} className={g.alert ? 'alert-row' : ''}>
                    <td>{tf('mon.' + slug(g.dimension), g.dimension)}: {tf('mon.' + slug(g.group), g.group)}</td>
                    <td>{g.n}</td>
                    {g.suppressed ? <td colSpan={3} className="muted">{t('fair.suppressed')}</td> : <><td>{Math.round(g.recommended * 100)}%</td><td>{Math.round(g.approved * 100)}%</td><td className="mono">{g.impact_ratio}</td></>}
                    <td>{g.alert ? <Badge status="high" /> : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {b && role !== 'auditor' && <StepFooter step="fairness" />}
    </>
  );
}
