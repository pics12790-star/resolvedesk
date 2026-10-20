import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import {readFileSync} from 'node:fs';
export default defineConfig(({mode})=>({
  plugins:[react(),{name:'font-license',generateBundle(){
    this.emitFile({type:'asset',fileName:'fonts/Inter-OFL.txt',source:readFileSync(new URL('./src/assets/Inter-OFL.txt',import.meta.url),'utf8')});
  }}],
  // Only the explicit walkthrough build ships the public, sanitized fixtures.
  publicDir:mode==='walkthrough'?'../../demo':false,
  define:mode==='walkthrough'?{'import.meta.env.VITE_APP_MODE':JSON.stringify('walkthrough')}:{},
  server:{proxy:{'/api':'http://127.0.0.1:8000'}},
}));
