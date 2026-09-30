import type { Role } from '../api';

export const ROLES: Role[] = ['candidate', 'counsellor', 'hr_reviewer', 'auditor'];
export const STAFF: Role[] = ['counsellor', 'hr_reviewer', 'auditor'];

export const ROLE_ICON: Record<Role, string> = {
  candidate: 'person-placeholder',
  counsellor: 'employee-approvals',
  hr_reviewer: 'business-card',
  auditor: 'inspect',
};

export type Step = 'profile' | 'evidence' | 'skills' | 'roles' | 'gaps' | 'learning' | 'employer' | 'fairness' | 'review' | 'passport';
export const STEPS: Step[] = ['profile', 'evidence', 'skills', 'roles', 'gaps', 'learning', 'employer', 'fairness', 'review', 'passport'];

export const STEP_ROUTE: Record<Step, string> = {
  profile: '/profile',
  evidence: '/evidence',
  skills: '/skills',
  roles: '/roles',
  gaps: '/gaps',
  learning: '/learning',
  employer: '/employer',
  fairness: '/fairness',
  review: '/review',
  passport: '/passport',
};

export const STEP_ICON: Record<Step, string> = {
  profile: 'shield',
  evidence: 'upload-to-cloud',
  skills: 'lightbulb',
  roles: 'target-group',
  gaps: 'map-2',
  learning: 'education',
  employer: 'building',
  fairness: 'compare',
  review: 'approvals',
  passport: 'document',
};

/** Which roles may open which screen. Everything else shows a friendly "this page is for..." panel. */
export const ROUTE_ACCESS: Record<string, Role[]> = {
  '/': ROLES,
  '/profile': ['candidate'],
  '/evidence': ['candidate', 'counsellor'],
  '/working': ROLES,
  '/skills': ['candidate', 'counsellor'],
  '/roles': ['candidate', 'counsellor'],
  '/gaps': ['candidate', 'counsellor'],
  '/learning': ['candidate', 'counsellor'],
  '/employer': ['candidate', 'counsellor', 'hr_reviewer'],
  '/fairness': ROLES,
  '/review': ['candidate', 'counsellor', 'hr_reviewer'],
  '/passport': ['candidate', 'counsellor', 'hr_reviewer'],
  '/activity': ROLES,
  '/architecture': ROLES,
  '/practice': ROLES,
};

export const canOpen = (route: string, role: Role) => (ROUTE_ACCESS[route] ?? ROLES).includes(role);
export const stepsFor = (role: Role) => STEPS.filter((s) => canOpen(STEP_ROUTE[s], role));

export const MORE_ITEMS = [
  { route: '/activity', key: 'nav.activity', icon: 'process' },
  { route: '/architecture', key: 'nav.architecture', icon: 'overview-chart' },
];
export const homeFor = (role: Role) => (role === 'auditor' ? '/activity' : role === 'hr_reviewer' ? '/review' : role === 'counsellor' ? '/review' : '/');
