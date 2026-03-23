import { createContext, useContext, useState, type ReactNode } from 'react'

interface HandbookContextValue {
  /** 現在表示中の指標ID（nullなら非表示） */
  activeHandbookId: string | null
  /** Drawerを開く */
  openHandbook: (indicatorId: string) => void
  /** Drawerを閉じる */
  closeHandbook: () => void
}

const HandbookContext = createContext<HandbookContextValue>({
  activeHandbookId: null,
  openHandbook: () => {},
  closeHandbook: () => {},
})

export function HandbookProvider({ children }: { children: ReactNode }) {
  const [activeHandbookId, setActiveHandbookId] = useState<string | null>(null)

  const openHandbook = (indicatorId: string) => {
    setActiveHandbookId(indicatorId)
  }

  const closeHandbook = () => {
    setActiveHandbookId(null)
  }

  return (
    <HandbookContext.Provider value={{ activeHandbookId, openHandbook, closeHandbook }}>
      {children}
    </HandbookContext.Provider>
  )
}

export function useHandbook() {
  return useContext(HandbookContext)
}
