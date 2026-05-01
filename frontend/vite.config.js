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
const runsRoot = path.resolve(repoRoot, 'runs')
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

        if (req.url?.startsWith('/api/reset-network')) {
          handleResetNetwork(req, res)
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

function handleResetNetwork(req, res) {
  if (req.method !== 'POST') {
    res.statusCode = 405
    res.setHeader('allow', 'POST')
    res.end('Method not allowed')
    return
  }

  try {
    resetNetworkFiles()
    sendJson(res, {
      reset: true,
      pendingInputs: pendingInputFiles(),
      message: 'Network reset, add Markdown files, then scan.',
    })
  } catch (error) {
    res.statusCode = 500
    sendJson(res, { reset: false, message: error.message })
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
      const processedNodeIds = compiledNodeIdsForInputs(pendingInputs)
      sendJson(res, {
        processed: true,
        pendingInputs,
        processedNodeIds,
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

function resetNetworkFiles() {
  removeInsideRepo(brainRoot)
  for (const fileName of ['latest_report.md', 'trace.jsonl']) {
    removeInsideRepo(path.join(runsRoot, fileName))
  }
  removeInsideRepo(path.join(runsRoot, 'subagents'))
  fs.mkdirSync(brainRoot, { recursive: true })
  fs.mkdirSync(runsRoot, { recursive: true })
}

function removeInsideRepo(targetPath) {
  const resolvedTarget = path.resolve(targetPath)
  const relativePath = path.relative(repoRoot, resolvedTarget)
  if (!relativePath || relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
    throw new Error(`Refusing to delete unsafe path: ${resolvedTarget}`)
  }
  fs.rmSync(resolvedTarget, { recursive: true, force: true })
}

function pendingInputFiles() {
  if (!fs.existsSync(inputRoot)) return []
  return fs
    .readdirSync(inputRoot)
    .filter((fileName) => fileName.endsWith('.md'))
    .sort()
}

function compiledNodeIdsForInputs(inputFileNames) {
  return inputFileNames
    .map((inputFileName) => compiledNodeIdForInput(inputFileName))
    .filter(Boolean)
}

function compiledNodeIdForInput(inputFileName) {
  const sourcePath = path.join(brainRoot, 'sources', inputFileName)
  if (!fs.existsSync(sourcePath)) return null
  const sourceText = fs.readFileSync(sourcePath, 'utf8')
  const compiledMatch = sourceText.match(/## Compiled Into[\s\S]*?\]\(([^)]+)\)/)
  if (!compiledMatch) return null
  const compiledPath = path.resolve(path.dirname(sourcePath), compiledMatch[1])
  const relativePath = path.relative(brainRoot, compiledPath)
  if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) return null
  return relativePath.split(path.sep).join('/')
}

function runOrganizer() {
  return new Promise((resolve, reject) => {
    const configPath = writeScanConfig()
    const python = pythonForOrganizer()
    if (!python) {
      const error = new Error('Could not find a Python 3.11+ interpreter with Organizer LLM/LangSmith dependencies installed.')
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
    'python3.12',
    'python3.11',
    loginShellPython,
    'python3',
  ].filter(Boolean)

  organizerPython = candidates.find((candidate) => {
    const check = spawnSync(
      candidate,
      [
        '-c',
        [
          'import sys',
          'assert sys.version_info >= (3, 11)',
          'import yaml',
          'import langsmith',
          'import langchain_google_genai',
        ].join('; '),
      ],
      { cwd: repoRoot, encoding: 'utf8' },
    )
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
  reasoning_effort: high
  thinking_budget: 2048
  temperature: 0.2

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
