import smcContent from './smc.md?raw'

export interface TocNode {
  level: 2 | 3 | 4
  text: string
  slug: string
  children?: TocNode[]
}

export function slugify(text: string): string {
  const base = text
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\-]/g, '')
  return base || 'section'
}

function parseToc(md: string): TocNode[] {
  const lines = md.split('\n')
  const result: TocNode[] = []
  let currentH2: TocNode | null = null
  let currentH3: TocNode | null = null
  const slugCounts = new Map<string, number>()

  const uniqueSlug = (text: string): string => {
    const base = slugify(text)
    const count = slugCounts.get(base) ?? 0
    slugCounts.set(base, count + 1)
    return count === 0 ? base : `${base}-${count}`
  }

  let inCodeFence = false
  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (line.startsWith('```')) {
      inCodeFence = !inCodeFence
      continue
    }
    if (inCodeFence) continue

    const m2 = /^##\s+(.+)$/.exec(line)
    const m3 = /^###\s+(.+)$/.exec(line)
    const m4 = /^####\s+(.+)$/.exec(line)

    if (m2) {
      const text = m2[1].trim()
      currentH2 = { level: 2, text, slug: uniqueSlug(text), children: [] }
      currentH3 = null
      result.push(currentH2)
    } else if (m3 && currentH2) {
      const text = m3[1].trim()
      currentH3 = { level: 3, text, slug: uniqueSlug(text), children: [] }
      currentH2.children!.push(currentH3)
    } else if (m4) {
      const text = m4[1].trim()
      const node: TocNode = { level: 4, text, slug: uniqueSlug(text) }
      if (currentH3) currentH3.children!.push(node)
      else if (currentH2) currentH2.children!.push(node)
    }
  }

  return result
}

export const SMC_CONTENT: string = smcContent
export const SMC_TOC: TocNode[] = parseToc(smcContent)

function flattenSlugs(nodes: TocNode[]): string[] {
  const result: string[] = []
  for (const n of nodes) {
    result.push(n.slug)
    if (n.children) result.push(...flattenSlugs(n.children))
  }
  return result
}

export const SMC_SLUG_LIST: string[] = flattenSlugs(SMC_TOC)
