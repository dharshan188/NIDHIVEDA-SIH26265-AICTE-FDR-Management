import { useLocation } from 'react-router-dom';
import type { Role } from '../components/nav';

export function useRole(): { role: Role; base: string } {
  const seg = useLocation().pathname.split('/')[1] as Role;
  const role: Role = seg === 'institution' || seg === 'auditor' ? seg : 'aicte';
  return { role, base: `/${role}` };
}
