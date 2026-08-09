import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.CF_BASE || 'http://127.0.0.1:8090'
const EMAIL = process.env.CF_EMAIL || 'admin@corefighter.local'
const PASSWORD = process.env.CF_PASSWORD || 'admin12345'
const OUT = 'E:/Task Space/cw1/.tools/shots'
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 })

const errors = []
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(`console: ${m.text()}`)
})
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
page.on('response', (r) => {
  if (r.status() >= 400) errors.push(`http ${r.status()} ${r.url()}`)
})

async function shot(name) {
  await page.waitForTimeout(1200)
  await page
    .waitForFunction(
      () => Array.from(document.images).every((i) => i.complete),
      null,
      { timeout: 20000 },
    )
    .catch(() => console.log('  (images still loading)'))
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('shot', name)
}

await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
await shot('01-login')

await page.fill('input[type=email]', EMAIL)
await page.fill('input[type=password]', PASSWORD)
await page.click('.cf-login__submit')
await page.waitForSelector('.cf-header', { timeout: 20000 })
await page.waitForTimeout(2500)
await shot('02-articles')

await page.click('text=新規記事を作成')
await page.waitForSelector('.cf-steps', { timeout: 15000 })
await shot('03-generate-step1')

await page.goto(`${BASE}/#/articles`)
await page.waitForSelector('.cf-card', { timeout: 20000 })
await page.click('.cf-card .cf-btn--navy')
await page.waitForSelector('.cf-steps', { timeout: 20000 })
await page.waitForFunction(() => !document.body.innerText.includes('記事を読み込んでいます'), null, {
  timeout: 30000,
})
await page.waitForTimeout(1500)
await shot('06-generate-existing')

await page.goto(`${BASE}/#/admin`)
await page.waitForTimeout(2500)
await shot('04-admin')

await page.goto(`${BASE}/#/ops`)
await page.waitForTimeout(9000)
await shot('05-ops')

console.log('--- issues ---')
console.log(errors.length ? [...new Set(errors)].join('\n') : 'none')
await browser.close()
