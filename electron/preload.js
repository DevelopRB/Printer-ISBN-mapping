/**
 * Preload — minimal bridge. No Node APIs, no secrets, no printer passwords.
 */
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('printingReconciliation', {
  platform: process.platform,
  isDesktop: true,
})
