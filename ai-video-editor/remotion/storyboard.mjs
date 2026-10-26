// Renders storyboard frames through the real composition (captions, hook, zoom included).
// usage: node storyboard.mjs <edit.json> <outDir> <frame> [<frame> ...]
import path from 'node:path';
import fs from 'node:fs';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const [editPath, outDir, ...frames] = process.argv.slice(2);
const inputProps = JSON.parse(fs.readFileSync(editPath, 'utf8'));
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const browserExecutable = process.env.REMOTION_BROWSER || null;
const composition = await selectComposition({serveUrl, id: 'Edit', inputProps, browserExecutable});
fs.mkdirSync(outDir, {recursive: true});
for (const [i, f] of frames.entries()) {
  await renderStill({
    composition, serveUrl, inputProps, browserExecutable,
    frame: Math.min(Number(f), composition.durationInFrames - 1),
    output: path.join(outDir, `${String(i).padStart(3, '0')}.jpg`),
    imageFormat: 'jpeg', jpegQuality: 80, scale: 0.25,
  });
}
console.log(`rendered ${frames.length} storyboard frames`);
