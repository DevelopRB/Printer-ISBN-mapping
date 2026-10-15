/**
 * Preload — minimal bridge. No Node APIs, no secrets, no printer passwords.
 */
const { contextBridge } = require('electron')

const versionArg = process.argv.find((arg) => arg.startsWith('--app-version='))

contextBridge.exposeInMainWorld('printingReconciliation', {
  platform: process.platform,
  isDesktop: true,
  version: versionArg ? versionArg.slice('--app-version='.length) : null,
})
