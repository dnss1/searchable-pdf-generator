import fs from 'fs'
import path from 'path'
import EditorClient from './EditorClient'

// Static export (GitHub Pages) needs every editor URL at build time:
// one per pre-processed demo document listed in public/demo-api.
export function generateStaticParams() {
  const samplesFile = path.join(process.cwd(), 'public', 'demo-api', 'api', 'demo', 'samples.json')
  if (!fs.existsSync(samplesFile)) return []
  const samples: Array<{ job_id: string }> = JSON.parse(fs.readFileSync(samplesFile, 'utf-8'))
  return samples.map((s) => ({ jobId: s.job_id }))
}

export default function EditorPage() {
  return <EditorClient />
}
