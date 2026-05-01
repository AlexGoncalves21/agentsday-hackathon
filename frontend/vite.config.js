import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const brainRoot = path.resolve(repoRoot, 'brain')
const inputRoot = path.resolve(repoRoot, 'input')
const graphPath = path.resolve(brainRoot, 'graph.json')
let organizerPython = null

function brainStaticPlugin() {
  return {
    name: 'brain-static-plugin',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url?.startsWith('/api/scan-input')) {
          handleScanInput(req, res)
          return
        }

        if (!req.url?.startsWith('/brain/')) {
          next()
          return
        }

        const url = new URL(req.url, 'http://localhost')
        const rel = decodeURIComponent(url.pathname.replace(/^\/brain\//, ''))
        const filePath = path.resolve(brainRoot, rel)
        const relativePath = path.relative(brainRoot, filePath)

        if (relativePath.startsWith('..') || path.isAbsolute(relativePath) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
          res.statusCode = 404
          res.end('Not found')
          return
        }

        if (filePath.endsWith('.json')) res.setHeader('content-type', 'application/json')
        if (filePath.endsWith('.md')) res.setHeader('content-type', 'text/markdown; charset=utf-8')
        fs.createReadStream(filePath).pipe(res)
      })
    },
  }
}

function handleScanInput(req, res) {
  if (req.method === 'GET') {
    const pendingInputs = pendingInputFiles()
    sendJson(res, {
      pendingInputs,
      message: pendingInputs.length
        ? `Found ${pendingInputs.length} new input file${pendingInputs.length === 1 ? '' : 's'}.`
        : 'No new input Markdown files found.',
    })
    return
  }

  if (req.method !== 'POST') {
    res.statusCode = 405
    res.setHeader('allow', 'GET, POST')
    res.end('Method not allowed')
    return
  }

  const pendingInputs = pendingInputFiles()
  if (!pendingInputs.length) {
    sendJson(res, { processed: false, pendingInputs: [], message: 'No new input Markdown files found.' })
    return
  }

  runOrganizer()
    .then((result) => {
      sendJson(res, {
        processed: true,
        pendingInputs,
        message: `Processed ${pendingInputs.length} input file${pendingInputs.length === 1 ? '' : 's'}.`,
        output: result.output,
      })
    })
    .catch((error) => {
      res.statusCode = 500
      sendJson(res, {
        processed: false,
        pendingInputs,
        message: 'Processing new files...',
        output: error.output || '',
      })
    })
}

function pendingInputFiles() {
  if (!fs.existsSync(inputRoot)) return []
  const graphMtime = fs.existsSync(graphPath) ? fs.statSync(graphPath).mtimeMs : 0
  return fs
    .readdirSync(inputRoot)
    .filter((fileName) => fileName.endsWith('.md'))
    .filter((fileName) => {
      const inputPath = path.join(inputRoot, fileName)
      const sourcePath = path.join(brainRoot, 'sources', fileName)
      return fs.statSync(inputPath).mtimeMs > graphMtime || !fs.existsSync(sourcePath)
    })
    .sort()
}

function runOrganizer() {
  return new Promise((resolve, reject) => {
    const configPath = writeScanConfig()
    const python = pythonForOrganizer()
    if (!python) {
      const error = new Error('Could not find a Python interpreter with PyYAML installed.')
      error.output = ''
      reject(error)
      return
    }
    const child = spawn(python, ['-m', 'agents.organizer.second_brain_agent', 'run', '--config', configPath], {
      cwd: repoRoot,
      env: process.env,
    })
    let output = ''
    child.stdout.on('data', (chunk) => {
      output += chunk.toString()
    })
    child.stderr.on('data', (chunk) => {
      output += chunk.toString()
    })
    child.on('error', (error) => {
      error.output = output
      reject(error)
    })
    child.on('close', (code) => {
      if (code === 0) {
        fs.rmSync(configPath, { force: true })
        resolve({ output })
        return
      }
      fs.rmSync(configPath, { force: true })
      const error = new Error(`Organizer exited with code ${code}`)
      error.output = output
      reject(error)
    })
  })
}

function pythonForOrganizer() {
  if (organizerPython) return organizerPython
  const loginShellPython = spawnSync('/bin/zsh', ['-lc', 'command -v python3'], { encoding: 'utf8' }).stdout.trim()
  const candidates = [
    process.env.ORGANIZER_PYTHON,
    process.env.PYTHON,
    path.join(os.homedir(), 'miniconda3/bin/python3'),
    path.join(os.homedir(), 'anaconda3/bin/python3'),
    path.join(repoRoot, '.venv/bin/python'),
    path.join(repoRoot, '.venv/bin/python3'),
    loginShellPython,
    'python3',
  ].filter(Boolean)

  organizerPython = candidates.find((candidate) => {
    const check = spawnSync(candidate, ['-c', 'import yaml'], { cwd: repoRoot, encoding: 'utf8' })
    return check.status === 0
  })
  return organizerPython
}

function writeScanConfig() {
  const configPath = path.join(os.tmpdir(), `agentsday-scan-${Date.now()}.yaml`)
  fs.writeFileSync(
    configPath,
    `mode: scan

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview

loop:
  max_iterations: 3
`,
  )
  return configPath
}

function sendJson(res, payload) {
  res.setHeader('content-type', 'application/json')
  res.end(JSON.stringify(payload))
}

export default defineConfig({
  plugins: [react(), brainStaticPlugin()],
  server: {
    port: 5173,
    strictPort: false,
  },
})
