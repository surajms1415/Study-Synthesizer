const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const kill = require('tree-kill');
const http = require('http');
const fs = require('fs');

let mainWindow;
let backendProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    autoHideMenuBar: true
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url.startsWith('http') && !url.includes('127.0.0.1:3000')) {
      event.preventDefault();
      require('electron').shell.openExternal(url);
    }
  });

  // Next.js static export loads best from a local web server to resolve absolute /_next paths
  // We'll spin up a quick express-like server using http
  
  const frontendPath = app.isPackaged 
      ? path.join(process.resourcesPath, 'frontend') 
      : path.join(__dirname, '../frontend/out');
      
  const mimeTypes = {
      '.html': 'text/html',
      '.js': 'text/javascript',
      '.css': 'text/css',
      '.json': 'application/json',
      '.png': 'image/png',
      '.jpg': 'image/jpg',
      '.gif': 'image/gif',
      '.svg': 'image/svg+xml',
      '.ico': 'image/x-icon',
  };

  const server = http.createServer((request, response) => {
      let filePath = path.join(frontendPath, request.url === '/' ? 'index.html' : request.url);
      
      // If no extension, try adding .html (Next.js routing)
      if (!path.extname(filePath)) {
          if (fs.existsSync(filePath + '.html')) {
              filePath += '.html';
          } else if (fs.existsSync(path.join(filePath, 'index.html'))) {
              filePath = path.join(filePath, 'index.html');
          }
      }

      const extname = String(path.extname(filePath)).toLowerCase();
      const contentType = mimeTypes[extname] || 'application/octet-stream';

      fs.readFile(filePath, (error, content) => {
          if (error) {
              if(error.code == 'ENOENT') {
                  // SPA fallback to index.html
                  fs.readFile(path.join(frontendPath, 'index.html'), (error2, content2) => {
                      response.writeHead(200, { 'Content-Type': 'text/html' });
                      response.end(content2, 'utf-8');
                  });
              }
              else {
                  response.writeHead(500);
                  response.end('Sorry, error: '+error.code+' ..\n');
                  response.end(); 
              }
          }
          else {
              response.writeHead(200, { 'Content-Type': contentType });
              response.end(content, 'utf-8');
          }
      });
  });

  server.listen(3000, '127.0.0.1', () => {
    mainWindow.loadURL('http://127.0.0.1:3000/');
  });
}

function startBackend() {
  const backendExePath = app.isPackaged
    ? path.join(process.resourcesPath, 'backend', 'backend_server.exe')
    : path.join(__dirname, '../backend/dist/backend_server.exe');

  console.log('Starting backend at:', backendExePath);
  
  if (fs.existsSync(backendExePath)) {
    backendProcess = spawn(backendExePath, [], { detached: false });
    // Process stdout/stderr commented out to prevent EPIPE broken pipe errors in packaged app
    // backendProcess.stdout.on('data', (data) => console.log(`Backend stdout: ${data}`));
    // backendProcess.stderr.on('data', (data) => console.error(`Backend stderr: ${data}`));
  } else {
    console.error(`Backend executable not found at ${backendExePath}. This is fine if running pure 'electron .' before building PyInstaller.`);
  }
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (backendProcess) {
    kill(backendProcess.pid, 'SIGKILL');
  }
});
