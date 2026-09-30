import type { Role } from '../api';
import { STEPS, STEP_ROUTE, type Step } from './roles';

export type StepState = 'done' | 'current' | 'todo';

export interface Journey {
  state: Record<Step, StepState>;
  available: Record<Step, boolean>;
  /** The next step the journey needs, and who has to do it. */
  next: Step;
  waitingFor: 'agents' | 'candidate' | 'reviewer' | 'none';
  finished: boolean;
}

/** Works out where the person is in the journey from the run state (kept simple on purpose). */
export function computeJourney(candidateId: string | null, run: any | null, visited: string[]): Journey {
  const v = run?.values ?? {};
  const seen = (s: Step) => visited.includes(STEP_ROUTE[s]);
  const available: Record<Step, boolean> = {
    profile: true,
    evidence: !!candidateId,
    skills: !!v.discovery,
    roles: !!v.ranking,
    gaps: !!v.pathway,
    learning: !!v.pathway,
    employer: !!v.employer_scan,
    fairness: !!v.bias_audit,
    review: !!v.review_task || !!v.final_review,
    passport: !!v.passport,
  };
  const done: Record<Step, boolean> = {
    profile: !!candidateId,
    evidence: !!run,
    skills: !!v.candidate_review,
    roles: !!v.selected_role_id,
    gaps: !!v.pathway && seen('gaps'),
    learning: !!v.pathway && seen('learning'),
    employer: !!v.employer_scan && seen('employer'),
    fairness: !!v.bias_audit && seen('fairness'),
    review: !!v.final_review,
    passport: !!v.passport && seen('passport'),
  };
  const firstOpen = STEPS.find((s) => !done[s]);
  // Steps that need the agents to finish first are "current" only once their data exists.
  const nextStep = (STEPS.find((s) => !done[s] && available[s]) ?? firstOpen ?? 'passport') as Step;
  const state = Object.fromEntries(STEPS.map((s) => [s, done[s] ? 'done' : s === nextStep ? 'current' : 'todo'])) as Record<Step, StepState>;
  const it = run?.interrupt?.checkpoint;
  const status = run?.run?.status;
  const waitingFor: Journey['waitingFor'] =
    status === 'running' ? 'agents' : it === 'candidate_review' || it === 'role_selection' || it === 'evidence_request' ? 'candidate' : it === 'final_review' ? 'reviewer' : 'none';
  return { state, available, next: nextStep, waitingFor, finished: !!v.passport };
}

export const nextRoute = (j: Journey) => STEP_ROUTE[j.next];

/** What the "next step" bar should say for this person right now. */
export interface NextHint {
  kind: 'start' | 'evidence' | 'agents' | 'your_turn' | 'wait_candidate' | 'wait_reviewer' | 'done' | 'view';
  route: string;
  actor?: Role;
}

export function nextHint(role: Role, candidateId: string | null, run: any | null, j: Journey): NextHint {
  const it = run?.interrupt?.checkpoint;
  if (role === 'auditor') return { kind: 'view', route: '/activity' };
  if (!candidateId) return { kind: 'start', route: '/profile', actor: 'candidate' };
  if (!run) return { kind: 'evidence', route: '/evidence', actor: 'candidate' };
  if (j.waitingFor === 'agents') return { kind: 'agents', route: '/working' };
  if (it === 'candidate_review') return role === 'candidate' ? { kind: 'your_turn', route: '/skills', actor: 'candidate' } : { kind: 'wait_candidate', route: '/skills', actor: 'candidate' };
  if (it === 'role_selection') return role === 'candidate' ? { kind: 'your_turn', route: '/roles', actor: 'candidate' } : { kind: 'wait_candidate', route: '/roles', actor: 'candidate' };
  if (it === 'evidence_request') return role === 'candidate' ? { kind: 'your_turn', route: '/review', actor: 'candidate' } : { kind: 'wait_candidate', route: '/review', actor: 'candidate' };
  if (it === 'final_review') {
    const mine = role === 'counsellor';
    // Until the candidate has looked at the results, guide them through the pages first.
    if (role === 'candidate' && j.next !== 'review') return { kind: 'view', route: STEP_ROUTE[j.next] };
    return mine ? { kind: 'your_turn', route: '/review', actor: role } : { kind: 'wait_reviewer', route: '/review', actor: 'counsellor' };
  }
  if (run?.values?.passport) return { kind: 'done', route: '/passport' };
  return { kind: 'view', route: STEP_ROUTE[j.next] };
}
