import { useCallback, useEffect, useState } from 'react';
import { hashDaRota, rotaDoHash, type Rota, type Tela } from './rotas';

/** A rota atual, lida do hash, e um jeito de mudar de tela. */
export function useRota(): Rota & { navegar: (tela: Tela, sub?: string | null) => void } {
  const [rota, setRota] = useState<Rota>(() => rotaDoHash(window.location.hash));

  useEffect(() => {
    const aoMudar = () => setRota(rotaDoHash(window.location.hash));
    window.addEventListener('hashchange', aoMudar);
    return () => window.removeEventListener('hashchange', aoMudar);
  }, []);

  const navegar = useCallback((tela: Tela, sub?: string | null) => {
    window.location.hash = hashDaRota(tela, sub);
  }, []);

  return { ...rota, navegar };
}
