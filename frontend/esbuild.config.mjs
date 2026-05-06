import * as esbuild from "esbuild";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const watch = process.argv.includes("--watch");

const ctx = await esbuild.context({
  entryPoints: ["src/main.jsx"],
  bundle: true,
  outfile: "dist/bundle.js",
  format: "iife",
  globalName: "NeonWhiteApp",
  jsx: "automatic",
  jsxImportSource: "react",
  loader: { ".jsx": "jsx", ".js": "js", ".css": "css" },
  define: {
    "process.env.NODE_ENV": '"production"',
  },
  minify: !watch,
  sourcemap: watch ? "inline" : false,
  logLevel: "info",
});

// Copy index.html to dist/
const distDir = path.join(__dirname, "dist");
fs.mkdirSync(distDir, { recursive: true });
fs.copyFileSync(
  path.join(__dirname, "src", "index.html"),
  path.join(distDir, "index.html")
);

if (watch) {
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await ctx.rebuild();
  await ctx.dispose();
  console.log("Build complete → dist/");
}
