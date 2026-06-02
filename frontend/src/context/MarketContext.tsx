import { createContext, useContext, useState, ReactNode } from 'react'

interface MarketCtx {
  market: string | undefined
  setMarket: (m: string | undefined) => void
}

const Ctx = createContext<MarketCtx>({ market: undefined, setMarket: () => {} })

export function MarketProvider({ children }: { children: ReactNode }) {
  const [market, setMarket] = useState<string | undefined>(undefined)
  return <Ctx.Provider value={{ market, setMarket }}>{children}</Ctx.Provider>
}

export const useMarket = () => useContext(Ctx)
