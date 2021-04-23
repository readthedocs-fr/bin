const { readFile, rename, unlink, writeFile } = require('fs/promises');
const { join, extname, basename } = require('path');
const { createHash } = require('crypto');
const { gzipSync } = require('zlib');
const cssnano = require('cssnano');
const { default: postcss } = require('postcss');
const glob = require('fast-glob');
const terser = require('terser');
const { optimize } = require('svgo');
const meow = require('meow');

// CSS Minfier
const cssm = postcss([cssnano({ preset: 'advanced' })]);

const matchers = {
  js: [/<script.*src=["']([\w/.-]+)["']/gi, (file, from) => terser.minify({ [from]: file.toString() }).then(({ code }) => code)],
  css: [
    /<link.*(?:rel=["']?stylesheet["']?.*href=["']([\w/.-]+)["']|href=["']([\w/.-]+)["'].*rel=["']?stylesheet["']?).*/gi,
    (file, from) => cssm.process(file.toString(), { map: false, from }).then(({ css }) => css),
  ],
  other: [/<link.*href=["']([\w/.-]+\.ico)["']/gi, (file) => file],
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// TODO: merge scripts and styles (1 script/style file per page)
async function bundle([assetDirectory, htmlGlob], { gzip, svgo }) {
  if (!assetDirectory || !htmlGlob) {
    throw new Error('The assetDirectory or htmlGlob is missing.')
  }

  const htmlPaths = await glob(htmlGlob);

  if (htmlPaths.length === 0) {
    throw new Error('Found 0 HTML file');
  }

  const htmlFiles = {};
  const changes = {
    js: {},
    css: {},
    other: {},
  };

  let n = 0;
  const assetRegEx = new RegExp(`^/${basename(assetDirectory)}`);
  for (const path of htmlPaths) {
    const file = await readFile(path, 'utf8');
    htmlFiles[path] = [file, false];

    for (const kind in changes) {
      const matcher = matchers[kind];
      for (const [, _match, match = _match] of file.matchAll(matcher[0])) {
        n++;
        const target = changes[kind];
        if (match in target) {
          target[match].push(path);
        } else {
          try {
            const from = join(assetDirectory, match.replace(assetRegEx, ''));
            target[match] = [await matcher[1](await readFile(from), from), from, path];
          } catch (error) {
            console.error(error);
            console.error(`At ${path} for ${kind.toUpperCase()} files : ${match}`)
            process.exit(1);
          }
        }
      }
    }
  }

  if (n === 0) {
    throw new Error('Found 0 match/change, aborting.');
  }

  for (const change in changes) {
    for (const path in changes[change]) {
      let [content, from, ...htmlPaths] = changes[change][path];

      const ext = extname(from);
      const hash = createHash('md5').update(content).digest('hex');
      const to = `${ext ? from.slice(0, from.lastIndexOf(ext)) : from}.${hash}${ext}`;

      if (gzip) {
        content = gzipSync(content, { level: gzip });
      }

      if (gzip || typeof content === 'string') { // js / css
        await writeFile(to, content);
        await unlink(from);
      } else { // other
        await rename(from, to);
      }

      for (const htmlPath of htmlPaths) {
        const ext = extname(path);
        htmlFiles[htmlPath][0] = htmlFiles[htmlPath][0].replace(
          new RegExp(`["']${escapeRegExp(path)}["']`, 'g'),
          `"${ext ? path.slice(0, path.lastIndexOf(ext)) : path}.${hash}${ext}"`,
        );
        changed = true;
      }
    }
  }

  for (const htmlPath in htmlFiles) {
    let [html, changed] = htmlFiles[htmlPath];
    if (svgo) {
      html = html.replace(/<svg.*>(.*)<\/svg>/gsi, (svg) => optimize(svg).data);
      changed = true;
    }

    if (changed) {
      await writeFile(htmlPath, html);
    }
  }

  console.log('Successfully bundled bin assets.');
}

const cli = meow(`
  Usage
    $ bin-bundler <assetDirectory> <htmlGlob>

  Options
    --gzip, -g  Gzip level compression (1-9), 0 mean disabled, 0 by default
    --svgo, -s  Minfiy and optimize (inline) SVGs, true by default`, {
  autoHelp: true,
  autoVersion: true,
  flags: {
    gzip: {
      type: 'number',
      alias: 'g',
      default: 0,
    },
    svgo: {
      type: 'boolean',
      alias: 's',
      default: true,
    },
  }
});

if (cli.flags.h) {
  return cli.showHelp();
}
if (cli.flags.v) {
  return cli.showVersion();
}
if (cli.input.length !== 2) {
  return cli.showHelp(1);
}

bundle(cli.input, cli.flags);
