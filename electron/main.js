/**
 * Electron main process — Printing Reconciliation
 *
 * Starts the FastAPI backend, waits for health, opens the UI.
 * Credentials stay in userData/.env (backend only) — never sent to renderer.
 */

const { app, BrowserWindow, dialog, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const net = require('net')
const { spawn } = require('child_process')

const APP_NAME = 'Printing Reconciliation'
const DEFAULT_PORT = 18765

/** @type {BrowserWindow | null} */
let mainWindow = null
/** @type {import('child_process').ChildProcess | null} */
let backendProcess = null
let chosenPort = DEFAULT_PORT
let isQuitting = false

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

function isDev() {
  return !app.isPackaged
}

function userDataPath(...parts) {
  return path.join(app.getPath('userData'), ...parts)
}

function resourcesPath(...parts) {
  if (isDev()) {
    return path.join(__dirname, '..', ...parts)
  }
  return path.join(process.resourcesPath, ...parts)
}

function ensureUserDataLayout() {
  const dataDir = userDataPath('data')
  const logsDir = userDataPath('logs')
  const uploads = path.join(dataDir, 'uploads')
  const downloads = path.join(dataDir, 'printer_downloads')
  for (const dir of [dataDir, logsDir, uploads, downloads]) {
    fs.mkdirSync(dir, { recursive: true })
  }

  const envTarget = userDataPath('.env')
  if (!fs.existsSync(envTarget)) {
    const candidates = [
      resourcesPath('printer.env'),
      resourcesPath('env.example'),
      path.join(__dirname, '..', '.env'),
      path.join(__dirname, '..', '.env.example'),
    ]
    for (const src of candidates) {
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, envTarget)
        break
      }
    }
    if (!fs.existsSync(envTarget)) {
      fs.writeFileSync(
        envTarget,
        [
          'PRINTER_1_USERNAME=admin',
          'PRINTER_1_PASSWORD=',
          'PRINTER_2_USERNAME=admin',
          'PRINTER_2_PASSWORD=',
          'PRINTER_3_USERNAME=admin',
          'PRINTER_3_PASSWORD=',
          'PRINTER_VERIFY_SSL=false',
          'PRINTER_JOBLOG_DEBUG=false',
          '',
        ].join('\n'),
        'utf8',
      )
    }
  }
  return { dataDir, logsDir, envTarget }
}

function findFreePort(startPort) {
  return new Promise((resolve) => {
    const tryPort = (port) => {
      const server = net.createServer()
      server.once('error', () => tryPort(port + 1))
      server.once('listening', () => {
        server.close(() => resolve(port))
      })
      server.listen(port, '127.0.0.1')
    }
    tryPort(startPort)
  })
}

function waitForHealth(port, timeoutMs = 90000) {
  const started = Date.now()
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        res.resume()
        if (res.statusCode === 200) {
          resolve(true)
          return
        }
        retry()
      })
      req.on('error', retry)
      req.setTimeout(2000, () => {
        req.destroy()
        retry()
      })
    }
    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        reject(new Error('Backend health check timed out'))
        return
      }
      setTimeout(attempt, 400)
    }
    attempt()
  })
}

function resolveBackendCommand() {
  if (isDev()) {
    const backendDir = path.join(__dirname, '..', 'backend')
    const python = path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    const script = path.join(backendDir, 'run_server.py')
    if (!fs.existsSync(python)) {
      throw new Error(
        'Development Python venv not found. Create backend/.venv and install requirements.',
      )
    }
    return {
      command: python,
      args: [script],
      cwd: backendDir,
      envExtra: {
        PRINTING_RECON_FRONTEND_DIST: path.join(__dirname, '..', 'frontend', 'dist'),
      },
    }
  }

  const exe = resourcesPath('backend', 'PrintingReconciliationAPI.exe')
  if (!fs.existsSync(exe)) {
    throw new Error('Packaged backend executable was not found.')
  }
  return {
    command: exe,
    args: [],
    cwd: path.dirname(exe),
    envExtra: {
      PRINTING_RECON_FRONTEND_DIST: resourcesPath('frontend'),
    },
  }
}

function startBackend(port, envPaths) {
  const { command, args, cwd, envExtra } = resolveBackendCommand()
  const env = {
    ...process.env,
    PRINTING_RECON_PACKAGED: isDev() ? '' : '1',
    PRINTING_RECON_HOST: '127.0.0.1',
    PRINTING_RECON_PORT: String(port),
    PRINTING_RECON_DATA_DIR: envPaths.dataDir,
    PRINTING_RECON_LOG_DIR: envPaths.logsDir,
    PRINTING_RECON_ENV_FILE: envPaths.envTarget,
    PRINTER_JOBLOG_DEBUG: 'false',
    PYTHONUNBUFFERED: '1',
    ...envExtra,
  }

  backendProcess = spawn(command, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  const logFile = path.join(envPaths.logsDir, 'electron-backend.log')
  const logStream = fs.createWriteStream(logFile, { flags: 'a' })
  logStream.write(
    `\n[${new Date().toISOString()}] starting backend\n` +
      `command=${command}\n` +
      `cwd=${cwd}\nexists=${fs.existsSync(command)}\n`,
  )
  backendProcess.stdout?.on('data', (d) => logStream.write(d))
  backendProcess.stderr?.on('data', (d) => logStream.write(d))
  backendProcess.on('error', (err) => {
    logStream.write(`[spawn error] ${err.message}\n`)
  })
  backendProcess.on('exit', (code, signal) => {
    logStream.write(`\n[exit] code=${code} signal=${signal}\n`)
    logStream.end()
    backendProcess = null
    if (!isQuitting && mainWindow) {
      dialog.showErrorBox(
        APP_NAME,
        'The application service stopped unexpectedly.\n\nPlease restart Printing Reconciliation.\nIf the problem continues, contact IT support.',
      )
    }
  })

  return backendProcess
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    const pid = backendProcess.pid
    try {
      if (process.platform === 'win32' && pid) {
        spawn('taskkill', ['/pid', String(pid), '/f', '/t'], {
          windowsHide: true,
          stdio: 'ignore',
        })
      } else {
        backendProcess.kill('SIGTERM')
      }
    } catch {
      // ignore
    }
  }
  backendProcess = null

  // Ensure no orphan API process remains (Windows)
  if (process.platform === 'win32') {
    try {
      spawn('taskkill', ['/IM', 'PrintingReconciliationAPI.exe', '/F', '/T'], {
        windowsHide: true,
        stdio: 'ignore',
      })
    } catch {
      // ignore
    }
  }
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 700,
    title: APP_NAME,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  return mainWindow.loadURL(`http://127.0.0.1:${port}/`)
}

app.whenReady().then(async () => {
  app.setName(APP_NAME)
  const envPaths = ensureUserDataLayout()
  chosenPort = await findFreePort(DEFAULT_PORT)

  try {
    startBackend(chosenPort, envPaths)
    await waitForHealth(chosenPort)
  } catch {
    stopBackend()
    const { response } = await dialog.showMessageBox({
      type: 'error',
      title: APP_NAME,
      message: 'Printing Reconciliation could not start.',
      detail: `Please contact IT support.\n\nLogs:\n${envPaths.logsDir}`,
      buttons: ['OK', 'Open Log Folder'],
      defaultId: 0,
      cancelId: 0,
    })
    if (response === 1) {
      shell.openPath(envPaths.logsDir)
    }
    app.quit()
    return
  }

  await createWindow(chosenPort)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(chosenPort)
    }
  })
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})

app.on('window-all-closed', () => {
  isQuitting = true
  stopBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
