const fs = require('fs');
const extract = require('/patches/node_modules/extract-zip-patched');

(async () => {
  const destination = '/tmp/extract-destination';
  try {
    await extract('/tmp/symlink.zip', {dir: destination});
    throw new Error('patched extract-zip accepted a symbolic-link entry');
  } catch (error) {
    if (!String(error).includes('Refusing symbolic link archive entry')) {
      throw error;
    }
  }
  if (fs.existsSync(`${destination}/escape`)) {
    throw new Error('patched extract-zip created the rejected symbolic link');
  }
  console.log('extract-zip symlink regression rejected before write');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
