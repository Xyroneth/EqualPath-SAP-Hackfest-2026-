import { useEffect } from 'react';
import { useApp } from './state';

/** Marks a journey page as seen once its content is available (drives the green ticks in the menu). */
export function useVisit(route: string, ready: boolean) {
  const { markVisited } = useApp();
  useEffect(() => {
    if (ready) markVisited(route);
  }, [ready, route, markVisited]);
}
