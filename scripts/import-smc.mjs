#!/usr/bin/env node
/**
 * SMC ハンドブックのソース文書を取り込む。
 *
 * 対応形式:
 *   - .docx (Microsoft Word / Google Docs エクスポート)  ← 推奨。画像を原寸抽出
 *   - .md   (Google Docs の Markdown エクスポート)        ← base64 画像対応
 *
 * 共通の処理:
 *   - 画像を `frontend/public/smc/images/` に書き出す（既存ファイルは一掃）
 *   - 画像参照を `/smc/images/<name>.<ext>` に書き換える
 *   - 結果を `frontend/src/content/guides/smc/smc.md` に上書き保存
 *
 * .docx を使う場合は pandoc が必要:
 *   winget install --id JohnMacFarlane.Pandoc
 *   その後ターミナルを再起動
 *
 * 使い方:
 *   node scripts/import-smc.mjs <入力ファイルへのパス>
 */
import { readFile, writeFile, mkdir, readdir, unlink, copyFile, rm } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { join, dirname, resolve, extname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { tmpdir } from 'node:os'

const execFileP = promisify(execFile)
const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const TARGET_MD = join(ROOT, 'frontend/src/content/guides/smc/smc.md')
const IMAGES_DIR = join(ROOT, 'frontend/public/smc/images')

const inputPath = process.argv[2]
if (!inputPath) {
  console.error('使い方: node scripts/import-smc.mjs <入力ファイル(.docx または .md)>')
  process.exit(1)
}
if (!existsSync(inputPath)) {
  console.error(`ファイルが見つかりません: ${inputPath}`)
  process.exit(1)
}

const ext = extname(inputPath).toLowerCase()

// 画像ディレクトリ初期化（.gitkeep は残す）
async function resetImagesDir() {
  await mkdir(IMAGES_DIR, { recursive: true })
  const existing = await readdir(IMAGES_DIR)
  for (const f of existing) {
    if (f === '.gitkeep') continue
    await unlink(join(IMAGES_DIR, f))
  }
}

// PATH の pandoc → なければ .vendor/pandoc/**/pandoc.exe を探す
async function findPandoc() {
  try {
    await execFileP('pandoc', ['--version'])
    return 'pandoc'
  } catch {}

  const vendorRoot = join(ROOT, '.vendor', 'pandoc')
  if (existsSync(vendorRoot)) {
    const stack = [vendorRoot]
    while (stack.length) {
      const dir = stack.pop()
      const entries = await readdir(dir, { withFileTypes: true })
      for (const e of entries) {
        const p = join(dir, e.name)
        if (e.isDirectory()) stack.push(p)
        else if (e.isFile() && (e.name === 'pandoc.exe' || e.name === 'pandoc')) return p
      }
    }
  }
  return null
}

async function ensurePandoc() {
  const bin = await findPandoc()
  if (!bin) {
    console.error('')
    console.error('✗ pandoc が見つかりません。')
    console.error('  Windows: winget install --id JohnMacFarlane.Pandoc')
    console.error('  または .vendor/pandoc/ に portable 版を配置してください。')
    console.error('  https://pandoc.org/installing.html')
    process.exit(1)
  }
  return bin
}

// .docx → pandoc で変換
async function importDocx() {
  const pandocBin = await ensurePandoc()

  const work = join(tmpdir(), `smc-import-${Date.now()}`)
  await mkdir(work, { recursive: true })

  const outMd = join(work, 'output.md')
  // --extract-media で画像を抽出（work/media/ 配下に配置される）
  await execFileP(pandocBin, [
    inputPath,
    '-f',
    'docx',
    '-t',
    'gfm',
    '--wrap=none',
    '--extract-media=' + work,
    '-o',
    outMd,
  ])

  await resetImagesDir()

  // pandoc が生成した media/ から画像をコピー
  const mediaDir = join(work, 'media')
  let count = 0
  if (existsSync(mediaDir)) {
    const files = await readdir(mediaDir)
    for (const f of files) {
      await copyFile(join(mediaDir, f), join(IMAGES_DIR, f))
      count++
    }
  }

  // MD 内のパス書換
  let md = await readFile(outMd, 'utf8')

  // 1. HTML <img src="..media/imageN.png" style="..." /> → ![](/smc/images/imageN.png)
  md = md.replace(
    /<img\s+[^>]*?src="[^"]*?[/\\]media[/\\]([^"]+)"[^>]*?\/?>/gs,
    '![](/smc/images/$1)',
  )

  // 2. Markdown ![](path/media/xxx) → ![](/smc/images/xxx)
  md = md.replace(/(!\[[^\]]*\]\()[^)]*?[/\\]media[/\\]([^)]+\))/g, '$1/smc/images/$2')

  // 3. Reference-style [name]: path/media/xxx → [name]: /smc/images/xxx
  md = md.replace(
    /(^\[[^\]]+\]:\s*<?)[^\s>]*?[/\\]media[/\\]([^\s>]+)>?/gm,
    '$1/smc/images/$2',
  )

  // 4. 空の見出し行を除去（Word の空段落に Heading スタイルが残ったケース）
  md = md.replace(/^#+\s*$/gm, '')

  // 5. 連続する空行を1つに圧縮
  md = md.replace(/\n{3,}/g, '\n\n')

  await mkdir(dirname(TARGET_MD), { recursive: true })
  await writeFile(TARGET_MD, md, 'utf8')

  // 後片付け
  await rm(work, { recursive: true, force: true })

  return count
}

// .md (Google Docs エクスポート) → base64 画像を抽出
async function importMarkdown() {
  const md = await readFile(inputPath, 'utf8')

  const refDefRegex =
    /^(\[[^\]]+\]:)\s*<?data:image\/([a-zA-Z0-9+]+);base64,([A-Za-z0-9+/=]+)>?\s*$/gm

  await resetImagesDir()

  const replacements = []
  let count = 0
  for (const m of md.matchAll(refDefRegex)) {
    const [full, ref, mime, b64] = m
    const nameMatch = /^\[([^\]]+)\]:$/.exec(ref)
    if (!nameMatch) continue
    const name = nameMatch[1]
    const fext = mime === 'jpeg' ? 'jpg' : mime === 'svg+xml' ? 'svg' : mime
    const filename = `${name}.${fext}`
    await writeFile(join(IMAGES_DIR, filename), Buffer.from(b64, 'base64'))
    replacements.push({ full, replacement: `[${name}]: /smc/images/${filename}` })
    count++
  }

  let converted = md
  for (const { full, replacement } of replacements) {
    converted = converted.replace(full, replacement)
  }

  await mkdir(dirname(TARGET_MD), { recursive: true })
  await writeFile(TARGET_MD, converted, 'utf8')

  return count
}

let count = 0
if (ext === '.docx') {
  console.log(`▶ pandoc で ${basename(inputPath)} を変換中...`)
  count = await importDocx()
} else if (ext === '.md') {
  console.log(`▶ Markdown ${basename(inputPath)} を取り込み中...`)
  console.warn('  注意: .md エクスポートは画像が縮小されます。可能なら .docx を使ってください。')
  count = await importMarkdown()
} else {
  console.error(`未対応の拡張子: ${ext}（.docx または .md を指定してください）`)
  process.exit(1)
}

console.log(`✓ 画像 ${count} 枚を書き出し: ${IMAGES_DIR}`)
console.log(`✓ Markdown を更新: ${TARGET_MD}`)
console.log('')
console.log('次のステップ: dev server をリロードして /smc を確認してください。')
